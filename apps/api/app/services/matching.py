"""Shipment ↔ carrier invoice line matching (tracking only, never amount-only)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import (
    CarrierInvoiceLine,
    MatchType,
    Organization,
    Shipment,
    ShipmentInvoiceMatch,
)

_TRACKING_NORM_RE = re.compile(r"[^A-Z0-9]+")

_sync_engine = None
_SyncSessionLocal: sessionmaker | None = None


def _sync_session_factory() -> sessionmaker:
    global _sync_engine, _SyncSessionLocal
    if _SyncSessionLocal is None:
        _sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
        _SyncSessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False)
    return _SyncSessionLocal


def normalize_tracking(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _TRACKING_NORM_RE.sub("", value.strip().upper())
    return cleaned or None


normalize_tracking_number = normalize_tracking


def tracking_numbers_match(*, shipment_tracking: str | None, invoice_tracking: str | None) -> bool:
    left = normalize_tracking(shipment_tracking)
    right = normalize_tracking(invoice_tracking)
    if not left or not right:
        return False
    return left == right


match_invoice_line_to_shipment = tracking_numbers_match
match_by_tracking = tracking_numbers_match


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


def _match_type_for_trackings(shipment_tracking: str | None, invoice_tracking: str | None) -> MatchType:
    ship_raw = (shipment_tracking or "").strip()
    inv_raw = (invoice_tracking or "").strip()
    if ship_raw and inv_raw and ship_raw == inv_raw:
        return MatchType.exact
    return MatchType.normalized


def persist_tracking_match(
    *,
    organization_id: uuid.UUID,
    shipment_id: uuid.UUID,
    carrier_invoice_line_id: uuid.UUID,
    shipment_tracking: str | None = None,
    invoice_tracking: str | None = None,
) -> ShipmentInvoiceMatch:
    with _sync_session_factory()() as session, session.begin():
        _sync_set_org(session, organization_id)
        _ensure_organization(session, organization_id)

        shipment = session.get(Shipment, shipment_id)
        if shipment is None:
            session.add(
                Shipment(
                    id=shipment_id,
                    organization_id=organization_id,
                    tracking_number=shipment_tracking,
                )
            )
        line = session.get(CarrierInvoiceLine, carrier_invoice_line_id)
        if line is None:
            session.add(
                CarrierInvoiceLine(
                    id=carrier_invoice_line_id,
                    organization_id=organization_id,
                    tracking_number=invoice_tracking,
                    billed_amount_minor=0,
                )
            )

        existing = session.scalar(
            select(ShipmentInvoiceMatch).where(
                ShipmentInvoiceMatch.organization_id == organization_id,
                ShipmentInvoiceMatch.carrier_invoice_line_id == carrier_invoice_line_id,
            )
        )
        if existing:
            return existing

        match = ShipmentInvoiceMatch(
            organization_id=organization_id,
            shipment_id=shipment_id,
            carrier_invoice_line_id=carrier_invoice_line_id,
            match_type=_match_type_for_trackings(shipment_tracking, invoice_tracking),
        )
        session.add(match)
        session.flush()
        session.refresh(match)
        return match


link_invoice_line_to_shipment = persist_tracking_match


def get_match_for_invoice_line(
    *,
    organization_id: uuid.UUID,
    carrier_invoice_line_id: uuid.UUID,
) -> ShipmentInvoiceMatch | dict[str, Any] | None:
    with _sync_session_factory()() as session, session.begin():
        _sync_set_org(session, organization_id)
        return session.scalar(
            select(ShipmentInvoiceMatch).where(
                ShipmentInvoiceMatch.organization_id == organization_id,
                ShipmentInvoiceMatch.carrier_invoice_line_id == carrier_invoice_line_id,
            )
        )


find_shipment_for_invoice_line = get_match_for_invoice_line


@dataclass
class MatchingRunResult:
    exact_matches: int
    normalized_matches: int
    skipped_already_matched: int


async def _matched_invoice_line_ids(session: AsyncSession, organization_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.scalars(
        select(ShipmentInvoiceMatch.carrier_invoice_line_id).where(
            ShipmentInvoiceMatch.organization_id == organization_id
        )
    )
    return set(rows.all())


async def _load_scope_rows(
    session: AsyncSession,
    organization_id: uuid.UUID,
    import_job_id: uuid.UUID | None,
) -> tuple[list[Shipment], list[CarrierInvoiceLine]]:
    ship_q = select(Shipment).where(Shipment.organization_id == organization_id)
    inv_q = select(CarrierInvoiceLine).where(CarrierInvoiceLine.organization_id == organization_id)
    if import_job_id is not None:
        ship_q = ship_q.where(Shipment.import_job_id == import_job_id)
        inv_q = inv_q.where(CarrierInvoiceLine.import_job_id == import_job_id)
    shipments = list((await session.scalars(ship_q)).all())
    invoice_lines = list((await session.scalars(inv_q)).all())
    return shipments, invoice_lines


async def run_automatic_matching(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    import_job_id: uuid.UUID | None = None,
) -> MatchingRunResult:
    already = await _matched_invoice_line_ids(session, organization_id)
    shipments, invoice_lines = await _load_scope_rows(session, organization_id, import_job_id)

    exact_matches = 0
    normalized_matches = 0
    skipped = 0

    unmatched_lines = [line for line in invoice_lines if line.id not in already]
    unmatched_shipments = list(shipments)

    exact_by_tracking: dict[str, list[Shipment]] = {}
    for shipment in unmatched_shipments:
        key = (shipment.tracking_number or "").strip()
        if not key:
            continue
        exact_by_tracking.setdefault(key, []).append(shipment)

    matched_shipment_ids: set[uuid.UUID] = set()

    for line in unmatched_lines:
        tracking = (line.tracking_number or "").strip()
        if not tracking:
            continue
        candidates = exact_by_tracking.get(tracking) or []
        shipment = next((s for s in candidates if s.id not in matched_shipment_ids), None)
        if shipment is None:
            continue
        session.add(
            ShipmentInvoiceMatch(
                organization_id=organization_id,
                shipment_id=shipment.id,
                carrier_invoice_line_id=line.id,
                match_type=MatchType.exact,
            )
        )
        matched_shipment_ids.add(shipment.id)
        already.add(line.id)
        exact_matches += 1

    norm_by_tracking: dict[str, list[Shipment]] = {}
    for shipment in unmatched_shipments:
        if shipment.id in matched_shipment_ids:
            continue
        key = normalize_tracking(shipment.tracking_number)
        if not key:
            continue
        norm_by_tracking.setdefault(key, []).append(shipment)

    for line in invoice_lines:
        if line.id in already:
            skipped += 1
            continue
        norm_key = normalize_tracking(line.tracking_number)
        if not norm_key:
            continue
        candidates = norm_by_tracking.get(norm_key) or []
        shipment = next((s for s in candidates if s.id not in matched_shipment_ids), None)
        if shipment is None:
            continue
        session.add(
            ShipmentInvoiceMatch(
                organization_id=organization_id,
                shipment_id=shipment.id,
                carrier_invoice_line_id=line.id,
                match_type=MatchType.normalized,
            )
        )
        matched_shipment_ids.add(shipment.id)
        already.add(line.id)
        normalized_matches += 1

    return MatchingRunResult(
        exact_matches=exact_matches,
        normalized_matches=normalized_matches,
        skipped_already_matched=skipped,
    )


async def create_manual_match(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    shipment_id: uuid.UUID,
    carrier_invoice_line_id: uuid.UUID,
) -> ShipmentInvoiceMatch:
    shipment = await session.scalar(
        select(Shipment).where(Shipment.id == shipment_id, Shipment.organization_id == organization_id)
    )
    line = await session.scalar(
        select(CarrierInvoiceLine).where(
            CarrierInvoiceLine.id == carrier_invoice_line_id,
            CarrierInvoiceLine.organization_id == organization_id,
        )
    )
    if not shipment or not line:
        raise ValueError("Shipment or invoice line not found for organization")

    existing = await session.scalar(
        select(ShipmentInvoiceMatch).where(
            ShipmentInvoiceMatch.organization_id == organization_id,
            ShipmentInvoiceMatch.carrier_invoice_line_id == carrier_invoice_line_id,
        )
    )
    if existing:
        return existing

    match = ShipmentInvoiceMatch(
        organization_id=organization_id,
        shipment_id=shipment.id,
        carrier_invoice_line_id=line.id,
        match_type=MatchType.manual,
    )
    session.add(match)
    await session.flush()
    return match
