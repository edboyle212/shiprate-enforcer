"""Service-layer and infra coverage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from app.config import _default_async_url, _default_sync_url, ai_enabled_globally
from app.db import set_rls_organization
from app.middleware.tenancy import TenancyMiddleware
from app.models import (
    CarrierInvoiceLine,
    Discrepancy,
    DisputeCase,
    DisputeCaseStatus,
    DisputeDraft,
    DisputeDraftStatus,
    MatchType,
    Organization,
    RateCardVersion,
    RateCardVersionStatus,
    Shipment,
    ShipmentInvoiceMatch,
    WmsPartner,
)
from app.services import disputes as dispute_service
from app.services.compliance import (
    build_rating_request,
    derive_reason_codes,
    evaluate_compliance,
    resolve_tolerances,
    run_compliance_for_matches,
    tolerance_threshold_minor,
    trace_summary,
    within_tolerance,
)
from app.services.matching import (
    _match_type_for_trackings,
    create_manual_match,
    normalize_tracking,
    run_automatic_matching,
)
from app.services.partner_profiles import get_partner_profile, upsert_partner_profile
from app.services.reporting import get_reporting_summary
from app.services.storage import StorageService, sha256_hex
from tests.conftest import ORG_ID


def test_all_models_reexport():
    from app.models import all_models

    assert "DisputeCase" in all_models.__all__
    assert all_models.Organization is not None


def test_config_database_url_variants(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TEST_APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    assert "asyncpg" in _default_async_url()
    assert _default_sync_url().startswith("postgresql://")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost/db")
    assert "asyncpg" in _default_async_url()
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    assert _default_sync_url().startswith("postgresql://user")
    monkeypatch.setenv("TEST_APP_DATABASE_URL", "postgresql://shiprate_app:shiprate@localhost/shiprate_test")
    assert _default_sync_url().startswith("postgresql://shiprate_app")
    monkeypatch.setenv("TEST_APP_DATABASE_URL", "postgresql+asyncpg://shiprate_app:shiprate@localhost/x")
    assert _default_sync_url().startswith("postgresql://shiprate_app")
    monkeypatch.setenv("TEST_APP_DATABASE_URL", "postgres://shiprate_app:shiprate@localhost/x")
    assert _default_sync_url().startswith("postgresql://shiprate_app")
    monkeypatch.delenv("TEST_APP_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)


def test_ai_enabled_globally_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHIPRATE_AI_ENABLED", "1")
    assert ai_enabled_globally() is True


@pytest.mark.asyncio
async def test_set_rls_organization():
    session = AsyncMock()
    await set_rls_organization(session, ORG_ID)
    session.execute.assert_awaited()
    await set_rls_organization(session, None)
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_reporting_summary_with_checks():
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[5, 1000, 2, 300, 50, 4, 10, 8])
    summary = await get_reporting_summary(session, ORG_ID)
    assert summary.discrepancy_count == 5
    assert summary.compliance_rate == 0.8
    assert summary.compliance_rate_note is None


@pytest.mark.asyncio
async def test_reporting_summary_no_checks_note():
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 0, 0, 0, 0, 0, 0, 0])
    summary = await get_reporting_summary(session, ORG_ID)
    assert summary.compliance_rate is None
    assert summary.compliance_rate_note == "No compliance checks yet"


def test_compliance_pure_helpers():
    tol = resolve_tolerances({"client_onboarding": {"tolerances": {"absolute_minor": 100, "percent": 1}}})
    assert tol.absolute_minor == 100
    assert tolerance_threshold_minor(10_000, tol) >= 100
    assert within_tolerance(10_050, 10_000, tol) is True
    ev = evaluate_compliance(billed_amount_minor=20_000, allowed_amount_minor=10_000, tolerance_percent=2.0)
    assert ev is not None
    codes = derive_reason_codes(trace={"minimum_charge_applied": True, "billable_weight_oz": 16}, variance_minor=50)
    assert "MINIMUM_CHARGE" in codes
    ship = Shipment(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        service_code="GND",
        dest_postal="90210",
        weight_oz=16,
        currency_code="USD",
    )
    rc = RateCardVersion(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json={},
        status=RateCardVersionStatus.approved,
    )
    req = build_rating_request(ship, rc)
    assert req["service_level"] == "GND"
    ts = trace_summary({"engine_version": "1", "rules_evaluated": {"table_key": "t1"}})
    assert ts["table_key"] == "t1"


def test_matching_helpers():
    assert normalize_tracking(" 1z-999 ") == "1Z999"
    assert _match_type_for_trackings("1Z", "1Z") == MatchType.exact
    assert _match_type_for_trackings("1Z", "1z") == MatchType.normalized


@pytest.mark.asyncio
async def test_run_automatic_matching_exact():
    session = AsyncMock()
    ship_id = uuid.uuid4()
    line_id = uuid.uuid4()
    shipment = Shipment(id=ship_id, organization_id=ORG_ID, tracking_number="1ZTRACK")
    line = CarrierInvoiceLine(id=line_id, organization_id=ORG_ID, tracking_number="1ZTRACK", billed_amount_minor=100)
    session.scalars = AsyncMock(
        side_effect=[
            MagicMock(all=list),
            MagicMock(all=lambda: [shipment]),
            MagicMock(all=lambda: [line]),
        ]
    )
    result = await run_automatic_matching(session, organization_id=ORG_ID)
    assert result.exact_matches == 1
    session.add.assert_called()


@pytest.mark.asyncio
async def test_create_manual_match_existing():
    session = AsyncMock()
    ship_id = uuid.uuid4()
    line_id = uuid.uuid4()
    existing = ShipmentInvoiceMatch(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        shipment_id=ship_id,
        carrier_invoice_line_id=line_id,
        match_type=MatchType.manual,
    )
    session.scalar = AsyncMock(
        side_effect=[
            Shipment(id=ship_id, organization_id=ORG_ID),
            CarrierInvoiceLine(id=line_id, organization_id=ORG_ID, billed_amount_minor=0),
            existing,
        ]
    )
    match = await create_manual_match(
        session, organization_id=ORG_ID, shipment_id=ship_id, carrier_invoice_line_id=line_id
    )
    assert match.id == existing.id


@pytest.mark.asyncio
async def test_run_compliance_for_matches_within_tolerance_passes():
    session = AsyncMock()
    match_id = uuid.uuid4()
    ship_id = uuid.uuid4()
    line_id = uuid.uuid4()
    match = ShipmentInvoiceMatch(
        id=match_id,
        organization_id=ORG_ID,
        shipment_id=ship_id,
        carrier_invoice_line_id=line_id,
        match_type=MatchType.exact,
    )
    shipment = Shipment(
        id=ship_id,
        organization_id=ORG_ID,
        carrier_code="UPS",
        service_code="GND",
        dest_postal="90210",
        weight_oz=16,
        currency_code="USD",
    )
    line = CarrierInvoiceLine(
        id=line_id,
        organization_id=ORG_ID,
        billed_amount_minor=500,
        currency_code="USD",
    )
    rc = RateCardVersion(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json={},
        status=RateCardVersionStatus.approved,
    )
    org = Organization(id=ORG_ID, name="o", slug="o", settings_json={})
    session.scalar = AsyncMock(side_effect=[org, None, rc])
    session.scalars = AsyncMock(return_value=MagicMock(all=lambda: [match]))
    session.get = AsyncMock(side_effect=lambda model, pk: shipment if pk == ship_id else line)
    session.flush = AsyncMock()

    result = await run_compliance_for_matches(session, organization_id=ORG_ID)
    assert result.checks_created == 1
    assert result.passed == 1
    assert result.discrepancies_created == 0


@pytest.mark.asyncio
async def test_run_compliance_for_matches_creates_discrepancy():
    session = AsyncMock()
    match_id = uuid.uuid4()
    ship_id = uuid.uuid4()
    line_id = uuid.uuid4()
    match = ShipmentInvoiceMatch(
        id=match_id,
        organization_id=ORG_ID,
        shipment_id=ship_id,
        carrier_invoice_line_id=line_id,
        match_type=MatchType.exact,
    )
    shipment = Shipment(
        id=ship_id,
        organization_id=ORG_ID,
        carrier_code="UPS",
        service_code="GND",
        dest_postal="90210",
        weight_oz=16,
        currency_code="USD",
    )
    line = CarrierInvoiceLine(
        id=line_id,
        organization_id=ORG_ID,
        billed_amount_minor=50_000,
        currency_code="USD",
    )
    rc = RateCardVersion(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json={},
        status=RateCardVersionStatus.approved,
    )
    org = Organization(id=ORG_ID, name="o", slug="o", settings_json={})
    session.scalar = AsyncMock(
        side_effect=[org, None, rc],
    )
    session.scalars = AsyncMock(return_value=MagicMock(all=lambda: [match]))
    session.get = AsyncMock(side_effect=lambda model, pk: shipment if pk == ship_id else line)
    session.flush = AsyncMock()

    result = await run_compliance_for_matches(session, organization_id=ORG_ID)
    assert result.checks_created == 1
    assert result.discrepancies_created == 1


@pytest.mark.asyncio
async def test_partner_profiles():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    assert await get_partner_profile(db, "northstar") == {}

    row = WmsPartner(partner_id="northstar", display_name="Northstar WMS", profile_json={"notes": "x"}, branding_json={"logo_url": "l"})
    db.scalar = AsyncMock(return_value=row)
    prof = await get_partner_profile(db, "northstar")
    assert prof["display_name"] == "Northstar WMS"

    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    out = await upsert_partner_profile(db, "new", {"partner_name": "New", "branding_mode": "co"})
    assert out["partner_id"] == "new"


@pytest.mark.asyncio
async def test_disputes_service_open_and_draft():
    session = AsyncMock()
    disc_id = uuid.uuid4()
    disc = Discrepancy(
        id=disc_id,
        organization_id=ORG_ID,
        compliance_check_id=uuid.uuid4(),
        billed_amount_minor=2000,
        allowed_amount_minor=1000,
        variance_minor=1000,
        currency_code="USD",
        reason_codes=["OVER_TOLERANCE"],
        trace_summary_json={"engine_version": "1"},
    )
    disc.dispute_case = None
    org = Organization(id=ORG_ID, name="o", slug="o", settings_json={})
    session.scalar = AsyncMock(side_effect=[disc, org])
    session.add = MagicMock()
    session.flush = AsyncMock()

    case = await dispute_service.open_dispute_case(session, organization_id=ORG_ID, discrepancy_id=disc_id)
    assert case.claim_amount_minor == 1000

    case_obj = DisputeCase(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        discrepancy_id=disc_id,
        claim_amount_minor=1000,
        currency_code="USD",
        status=DisputeCaseStatus.open,
        autonomy_tier="draft",
        fee_bps=2000,
    )
    case_obj.discrepancy = disc
    case_obj.drafts = []
    session.scalar = AsyncMock(return_value=case_obj)
    draft = await dispute_service.create_or_refresh_draft(
        session, organization_id=ORG_ID, dispute_case_id=case_obj.id
    )
    assert "DRAFT" in draft.email_body

    d1 = DisputeDraft(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=case_obj.id,
        email_subject="s",
        email_body="b",
        status=DisputeDraftStatus.draft,
        created_at=datetime.now(UTC),
    )
    case_obj.drafts = [d1]
    session.scalar = AsyncMock(return_value=case_obj)
    approved = await dispute_service.approve_draft(
        session, organization_id=ORG_ID, dispute_case_id=case_obj.id
    )
    assert approved.status == DisputeDraftStatus.approved


def test_storage_filesystem(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.storage.settings.local_upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.storage.settings.s3_endpoint_url", None)
    svc = StorageService()
    data = b"hello"
    assert sha256_hex(data) == sha256_hex(data)
    key, digest = svc.put_immutable(str(ORG_ID), "f.csv", data)
    assert svc.read_object(key) == data
    assert svc.backend_name == "filesystem"
    assert svc.list_etl_objects("p", str(ORG_ID), "shipments") == []


@pytest.mark.asyncio
async def test_tenancy_middleware_sets_header():
    middleware = TenancyMiddleware(app=MagicMock())

    async def call_next(request):
        from starlette.responses import Response

        return Response("ok")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-organization-id", str(ORG_ID).encode())],
    }
    request = Request(scope)
    response = await middleware.dispatch(request, call_next)
    assert response.headers.get("X-Organization-Id") == str(ORG_ID)


@pytest.mark.asyncio
async def test_etl_poll_drop_ingests(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app.services.etl_file_drop import poll_etl_drop

    monkeypatch.setattr("app.services.storage.settings.local_upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.storage.settings.s3_endpoint_url", None)
    monkeypatch.setattr("app.services.storage.settings.etl_drop_root", "etl-drops")
    drop = tmp_path / "etl-drops" / "northstar" / str(ORG_ID) / "shipments"
    drop.mkdir(parents=True)
    (drop / "file.csv").write_bytes(b"track\n1Z\n")

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    result = await poll_etl_drop(db, partner_id="northstar", organization_id=ORG_ID)
    assert len(result["ingested"]) == 1
    db.commit.assert_awaited()
