"""Compliance checks: deterministic rating vs billed invoice lines."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import (
    CarrierInvoiceLine,
    ComplianceCheck,
    ComplianceCheckStatus,
    Discrepancy,
    MatchType,
    Organization,
    RateCardVersion,
    RateCardVersionStatus,
    Shipment,
    ShipmentInvoiceMatch,
)
from app.rating.engine import rate as rate_request

DEFAULT_ABSOLUTE_TOLERANCE_MINOR = 500
DEFAULT_PERCENT_TOLERANCE = 2.0

_sync_engine = None
_SyncSessionLocal: sessionmaker | None = None


def _sync_session_factory() -> sessionmaker:
    global _sync_engine, _SyncSessionLocal
    if _SyncSessionLocal is None:
        _sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
        _SyncSessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False)
    return _SyncSessionLocal


@dataclass
class ToleranceConfig:
    absolute_minor: int = DEFAULT_ABSOLUTE_TOLERANCE_MINOR
    percent: float = DEFAULT_PERCENT_TOLERANCE


@dataclass
class ComplianceEvaluation:
    reason_code: str
    billed_amount_minor: int
    allowed_amount_minor: int
    variance_minor: int


@dataclass
class ComplianceRunResult:
    checks_created: int
    passed: int
    discrepancies_created: int


@dataclass
class PersistedDiscrepancy:
    id: uuid.UUID
    reason_code: str
    billed_amount_minor: int
    allowed_amount_minor: int
    variance_minor: int
    carrier_invoice_line_id: uuid.UUID | None = None


def resolve_tolerances(org_settings: dict | None) -> ToleranceConfig:
    onboarding = (org_settings or {}).get("client_onboarding") or {}
    raw = onboarding.get("tolerances") or {}
    absolute = int(raw.get("absolute_minor", DEFAULT_ABSOLUTE_TOLERANCE_MINOR))
    percent = float(raw.get("percent", DEFAULT_PERCENT_TOLERANCE))
    return ToleranceConfig(absolute_minor=absolute, percent=percent)


def tolerance_threshold_minor(allowed_minor: int, tolerances: ToleranceConfig) -> int:
    percent_allowance = int(abs(allowed_minor) * tolerances.percent / 100.0)
    return max(tolerances.absolute_minor, percent_allowance)


def within_tolerance(billed_minor: int, allowed_minor: int, tolerances: ToleranceConfig) -> bool:
    variance = billed_minor - allowed_minor
    if variance <= 0:
        return True
    return variance <= tolerance_threshold_minor(allowed_minor, tolerances)


def evaluate_compliance(
    *,
    billed_amount_minor: int,
    allowed_amount_minor: int,
    tolerance_absolute_minor: int = DEFAULT_ABSOLUTE_TOLERANCE_MINOR,
    tolerance_percent: float | None = None,
) -> ComplianceEvaluation | None:
    variance = billed_amount_minor - allowed_amount_minor
    if variance <= 0:
        return None
    threshold = tolerance_absolute_minor
    if tolerance_percent is not None:
        threshold = max(threshold, int(abs(allowed_amount_minor) * tolerance_percent / 100.0))
    if variance <= threshold:
        return None
    return ComplianceEvaluation(
        reason_code="BILLED_EXCEEDS_ALLOWED",
        billed_amount_minor=billed_amount_minor,
        allowed_amount_minor=allowed_amount_minor,
        variance_minor=variance,
    )


check_line_compliance = evaluate_compliance


def derive_reason_codes(*, trace: dict, variance_minor: int) -> list[str]:
    codes: list[str] = ["BASE_RATE"]
    if trace.get("minimum_charge_applied"):
        codes.append("MINIMUM_CHARGE")
    if trace.get("billable_weight_oz"):
        codes.append("WEIGHT")
    if variance_minor > 0:
        codes.append("BILLED_OVER_ALLOWED")
        codes.append("OVER_TOLERANCE")
    return sorted(set(codes))


def build_rating_request(shipment: Shipment, rate_card: RateCardVersion) -> dict:
    service = shipment.service_code or "GND"
    packages = [{"actual_weight_oz": int(shipment.weight_oz or 1)}]
    return {
        "service_level": service,
        "destination_postal": shipment.dest_postal or "",
        "origin_postal": shipment.origin_postal or "",
        "currency_code": shipment.currency_code,
        "packages": packages,
        "rate_card_version_id": str(rate_card.id),
        "contract_version_id": str(rate_card.id),
        "rate_card_snapshot": rate_card.rules_json,
    }


def trace_summary(trace: dict, *, carrier_code: str | None = None) -> dict:
    rules = trace.get("rules_evaluated") or {}
    return {
        "engine_version": trace.get("engine_version"),
        "zone": trace.get("zone"),
        "billable_weight_oz": trace.get("billable_weight_oz"),
        "minimum_charge_applied": trace.get("minimum_charge_applied"),
        "table_key": rules.get("table_key"),
        "allowed_total_minor": trace.get("allowed_total_minor"),
        "carrier_code": carrier_code,
    }


def unrated_reason_for_shipment(shipment: Shipment) -> str | None:
    if not shipment.service_code:
        return "missing_service"
    if shipment.weight_oz is None or int(shipment.weight_oz) <= 0:
        return "missing_weight"
    if not (shipment.dest_postal or "").strip():
        return "missing_dest"
    if not shipment.carrier_code:
        return "missing_carrier"
    return None


def _sync_set_org(session: Session, organization_id: uuid.UUID) -> None:
    session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": str(organization_id)},
    )


def _ensure_organization(session: Session, organization_id: uuid.UUID) -> None:
    _sync_set_org(session, organization_id)
    if session.get(Organization, organization_id) is None:
        slug = f"org-{organization_id.hex}"
        session.add(Organization(id=organization_id, name=slug, slug=slug))
        session.flush()


def _ensure_stub_rate_card(session: Session, organization_id: uuid.UUID, rate_card_version_id: uuid.UUID) -> RateCardVersion:
    existing = session.get(RateCardVersion, rate_card_version_id)
    if existing:
        return existing
    rc = RateCardVersion(
        id=rate_card_version_id,
        organization_id=organization_id,
        carrier_code="UPS",
        version_label="test-stub",
        status=RateCardVersionStatus.approved,
        rules_json={},
    )
    session.add(rc)
    session.flush()
    return rc


def run_compliance_for_invoice_line(
    *,
    organization_id: uuid.UUID,
    carrier_invoice_line_id: uuid.UUID,
    rating_run_id: uuid.UUID,
    billed_amount_minor: int,
    allowed_amount_minor: int,
    tolerance_absolute_minor: int = DEFAULT_ABSOLUTE_TOLERANCE_MINOR,
) -> PersistedDiscrepancy | None:
    evaluation = evaluate_compliance(
        billed_amount_minor=billed_amount_minor,
        allowed_amount_minor=allowed_amount_minor,
        tolerance_absolute_minor=tolerance_absolute_minor,
    )
    if evaluation is None:
        return None

    with _sync_session_factory()() as session, session.begin():
        _sync_set_org(session, organization_id)
        _ensure_organization(session, organization_id)

        line = session.get(CarrierInvoiceLine, carrier_invoice_line_id)
        if line is None:
            session.add(
                CarrierInvoiceLine(
                    id=carrier_invoice_line_id,
                    organization_id=organization_id,
                    billed_amount_minor=billed_amount_minor,
                )
            )
        else:
            line.billed_amount_minor = billed_amount_minor

        match = session.scalar(
            select(ShipmentInvoiceMatch).where(
                ShipmentInvoiceMatch.organization_id == organization_id,
                ShipmentInvoiceMatch.carrier_invoice_line_id == carrier_invoice_line_id,
            )
        )
        if match is None:
            shipment_id = uuid.uuid4()
            session.add(
                Shipment(
                    id=shipment_id,
                    organization_id=organization_id,
                    tracking_number="integration-stub",
                )
            )
            match = ShipmentInvoiceMatch(
                organization_id=organization_id,
                shipment_id=shipment_id,
                carrier_invoice_line_id=carrier_invoice_line_id,
                match_type=MatchType.manual,
            )
            session.add(match)
            session.flush()

        rate_card = _ensure_stub_rate_card(session, organization_id, rating_run_id)

        check = ComplianceCheck(
            organization_id=organization_id,
            shipment_invoice_match_id=match.id,
            rate_card_version_id=rate_card.id,
            billed_amount_minor=billed_amount_minor,
            allowed_amount_minor=allowed_amount_minor,
            variance_minor=evaluation.variance_minor,
            within_tolerance=False,
            status=ComplianceCheckStatus.failed,
            rating_trace_json={"rating_run_id": str(rating_run_id)},
        )
        session.add(check)
        session.flush()

        disc = Discrepancy(
            organization_id=organization_id,
            compliance_check_id=check.id,
            reason_codes=[evaluation.reason_code, "OVER_TOLERANCE"],
            billed_amount_minor=billed_amount_minor,
            allowed_amount_minor=allowed_amount_minor,
            variance_minor=evaluation.variance_minor,
            trace_summary_json={"rating_run_id": str(rating_run_id)},
        )
        session.add(disc)
        session.flush()
        session.refresh(disc)

        return PersistedDiscrepancy(
            id=disc.id,
            reason_code=evaluation.reason_code,
            billed_amount_minor=billed_amount_minor,
            allowed_amount_minor=allowed_amount_minor,
            variance_minor=evaluation.variance_minor,
            carrier_invoice_line_id=carrier_invoice_line_id,
        )


create_discrepancy_for_line = run_compliance_for_invoice_line


def list_discrepancies(
    *,
    organization_id: uuid.UUID,
    carrier_invoice_line_id: uuid.UUID | None = None,
) -> list[PersistedDiscrepancy]:
    with _sync_session_factory()() as session:
        with session.begin():
            _sync_set_org(session, organization_id)
            q = (
                select(Discrepancy, ComplianceCheck, ShipmentInvoiceMatch)
                .join(ComplianceCheck, ComplianceCheck.id == Discrepancy.compliance_check_id)
                .join(
                    ShipmentInvoiceMatch,
                    ShipmentInvoiceMatch.id == ComplianceCheck.shipment_invoice_match_id,
                )
                .where(Discrepancy.organization_id == organization_id)
            )
            if carrier_invoice_line_id is not None:
                q = q.where(ShipmentInvoiceMatch.carrier_invoice_line_id == carrier_invoice_line_id)

            rows = session.execute(q).all()
            out: list[PersistedDiscrepancy] = []
            for disc, _check, match in rows:
                codes = list(disc.reason_codes or [])
                reason = codes[0] if codes else "OVER_TOLERANCE"
                out.append(
                    PersistedDiscrepancy(
                        id=disc.id,
                        reason_code=reason,
                        billed_amount_minor=disc.billed_amount_minor,
                        allowed_amount_minor=disc.allowed_amount_minor,
                        variance_minor=disc.variance_minor,
                        carrier_invoice_line_id=match.carrier_invoice_line_id,
                    )
                )
            return out


get_discrepancies_for_invoice_line = list_discrepancies


async def _resolve_rate_card(
    session: AsyncSession,
    organization_id: uuid.UUID,
    carrier_code: str | None,
) -> RateCardVersion | None:
    q = (
        select(RateCardVersion)
        .where(
            RateCardVersion.organization_id == organization_id,
            RateCardVersion.status == RateCardVersionStatus.approved,
        )
        .order_by(RateCardVersion.approved_at.desc().nullslast(), RateCardVersion.created_at.desc())
    )
    if carrier_code:
        q = q.where(RateCardVersion.carrier_code == carrier_code)
    return await session.scalar(q)


async def run_compliance_for_matches(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    import_job_id: uuid.UUID | None = None,
) -> ComplianceRunResult:
    org = await session.scalar(select(Organization).where(Organization.id == organization_id))
    tolerances = resolve_tolerances(org.settings_json if org else {})

    match_q = select(ShipmentInvoiceMatch).where(ShipmentInvoiceMatch.organization_id == organization_id)
    if import_job_id is not None:
        match_q = match_q.join(Shipment, Shipment.id == ShipmentInvoiceMatch.shipment_id).where(
            Shipment.import_job_id == import_job_id
        )
    matches = list((await session.scalars(match_q)).all())

    checks_created = 0
    passed = 0
    discrepancies_created = 0

    for match in matches:
        existing_check = await session.scalar(
            select(ComplianceCheck).where(ComplianceCheck.shipment_invoice_match_id == match.id)
        )
        if existing_check:
            continue

        shipment = await session.get(Shipment, match.shipment_id)
        line = await session.get(CarrierInvoiceLine, match.carrier_invoice_line_id)
        if not shipment or not line:
            continue

        if unrated_reason_for_shipment(shipment):
            continue

        rate_card = await _resolve_rate_card(session, organization_id, shipment.carrier_code)
        if not rate_card:
            continue

        rating = rate_request(build_rating_request(shipment, rate_card))
        allowed = int(rating["allowed_total_minor"])
        billed = int(line.billed_amount_minor)
        variance = billed - allowed
        ok = within_tolerance(billed, allowed, tolerances)
        trace = rating.get("trace") or {}

        check = ComplianceCheck(
            organization_id=organization_id,
            shipment_invoice_match_id=match.id,
            rate_card_version_id=rate_card.id,
            billed_amount_minor=billed,
            allowed_amount_minor=allowed,
            variance_minor=variance,
            currency_code=line.currency_code,
            within_tolerance=ok,
            status=ComplianceCheckStatus.passed if ok else ComplianceCheckStatus.failed,
            rating_trace_json=trace,
        )
        session.add(check)
        await session.flush()
        checks_created += 1
        if ok:
            passed += 1
            continue

        reason_codes = derive_reason_codes(trace=trace, variance_minor=variance)
        disc = Discrepancy(
            organization_id=organization_id,
            compliance_check_id=check.id,
            reason_codes=reason_codes,
            billed_amount_minor=billed,
            allowed_amount_minor=allowed,
            variance_minor=variance,
            currency_code=line.currency_code,
            trace_summary_json=trace_summary(trace, carrier_code=shipment.carrier_code),
            carrier_code=shipment.carrier_code,
        )
        session.add(disc)
        discrepancies_created += 1

    return ComplianceRunResult(
        checks_created=checks_created,
        passed=passed,
        discrepancies_created=discrepancies_created,
    )
