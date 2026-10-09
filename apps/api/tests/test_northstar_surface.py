"""Coverage for Northstar / white-label partner and ETL file-drop surfaces."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models import (
    EtlProcessedObject,
    ImportJob,
    ImportJobStatus,
    Organization,
    SourceFile,
    SourceFileKind,
    WmsPartner,
)
from app.services.etl_file_drop import (
    _parse_amount_minor,
    poll_etl_drop,
    process_etl_pending_import_jobs,
)
from app.services.partner_profiles import upsert_partner_profile
from app.services.reporting import ReportingSummary
from tests.conftest import ORG_HEADER, ORG_ID

PREFIX = settings.api_prefix.rstrip("/")


def test_parse_amount_minor():
    assert _parse_amount_minor(None) == 0
    assert _parse_amount_minor("12.50") == 1250
    assert _parse_amount_minor("1,234.56") == 123456


@pytest.mark.asyncio
async def test_poll_etl_drop_skips_seen_object(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.storage.settings.local_upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.storage.settings.s3_endpoint_url", None)
    monkeypatch.setattr("app.services.storage.settings.etl_drop_root", "etl-drops")
    drop = tmp_path / "etl-drops" / "northstar" / str(ORG_ID) / "shipments"
    drop.mkdir(parents=True)
    (drop / "seen.csv").write_bytes(b"track\n1Z\n")

    seen = EtlProcessedObject(organization_id=ORG_ID, storage_key="etl-drops/northstar/x/shipments/seen.csv", sha256_hex="a")
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=seen)
    db.commit = AsyncMock()

    result = await poll_etl_drop(db, partner_id="northstar", organization_id=ORG_ID)
    assert result["skipped"]
    assert not result["ingested"]


@pytest.mark.asyncio
async def test_poll_etl_drop_reuses_existing_source_file(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.storage.settings.local_upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.storage.settings.s3_endpoint_url", None)
    monkeypatch.setattr("app.services.storage.settings.etl_drop_root", "etl-drops")
    drop = tmp_path / "etl-drops" / "northstar" / str(ORG_ID) / "invoices"
    drop.mkdir(parents=True)
    (drop / "inv.csv").write_bytes(b"tracking_number,billed_amount\n1Z,10.00\n")

    source_id = uuid.uuid4()
    existing = SourceFile(
        id=source_id,
        organization_id=ORG_ID,
        kind=SourceFileKind.carrier_invoice,
        original_filename="inv.csv",
        byte_size=10,
        sha256_hex="deadbeef",
        storage_key="immutable/inv.csv",
        storage_backend="local",
    )
    existing_job = ImportJob(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        source_file_id=source_id,
        idempotency_key="etl:etl-drops/northstar/x/invoices/inv.csv",
        sha256_hex="deadbeef",
        status=ImportJobStatus.pending,
    )

    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[None, existing, existing_job])
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()

    result = await poll_etl_drop(db, partner_id="northstar", organization_id=ORG_ID)
    assert len(result["ingested"]) == 1
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_process_etl_pending_import_jobs_shipments_and_invoices(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.storage.settings.local_upload_dir", str(tmp_path))
    monkeypatch.setattr("app.services.storage.settings.s3_endpoint_url", None)

    ship_key = f"{ORG_ID}/ship.csv"
    inv_key = f"{ORG_ID}/inv.csv"
    ship_csv = b"tracking_number,carrier,service,dest_postal,weight_oz\n1Z999,UPS,GROUND,10001,16\n"
    inv_csv = b"tracking_number,charge_code,description,billed_amount\n1Z999,FRT,Freight,15.50\n"
    storage: dict[str, bytes] = {ship_key: ship_csv, inv_key: inv_csv}

    def _read(key: str) -> bytes:
        return storage[key]

    monkeypatch.setattr("app.services.etl_file_drop.storage_service.read_object", _read)

    ship_job_id = uuid.uuid4()
    inv_job_id = uuid.uuid4()
    ship_source = SourceFile(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        kind=SourceFileKind.shipment_export,
        original_filename="ship.csv",
        byte_size=len(ship_csv),
        sha256_hex="s1",
        storage_key=ship_key,
        storage_backend="local",
    )
    inv_source = SourceFile(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        kind=SourceFileKind.carrier_invoice,
        original_filename="inv.csv",
        byte_size=len(inv_csv),
        sha256_hex="i1",
        storage_key=inv_key,
        storage_backend="local",
    )
    ship_job = ImportJob(
        id=ship_job_id,
        organization_id=ORG_ID,
        source_file_id=ship_source.id,
        idempotency_key="etl:drop/ship.csv",
        sha256_hex="s1",
        status=ImportJobStatus.pending,
    )
    inv_job = ImportJob(
        id=inv_job_id,
        organization_id=ORG_ID,
        source_file_id=inv_source.id,
        idempotency_key="etl:drop/inv.csv",
        sha256_hex="i1",
        status=ImportJobStatus.pending,
    )

    async def _scalars(_stmt):
        return SimpleNamespace(all=lambda: [ship_job, inv_job])

    async def _scalar(stmt):
        stmt_text = str(stmt)
        if (
            ("source_files" in stmt_text.lower() or "SourceFile" in stmt_text)
            and ship_job.source_file_id
            and inv_job.source_file_id
        ):
            # Resolve by job order in loop — first ship then inv
            if not hasattr(_scalar, "_n"):
                _scalar._n = 0
            _scalar._n += 1
            return ship_source if _scalar._n == 1 else inv_source
        return None

    db = AsyncMock()
    db.scalars = _scalars
    db.scalar = _scalar
    db.commit = AsyncMock()
    db.add = MagicMock()

    result = await process_etl_pending_import_jobs(db, organization_id=ORG_ID)
    assert result["jobs_completed"] == 2
    assert result["shipments_created"] == 1
    assert result["invoice_lines_created"] == 1


@pytest.mark.asyncio
async def test_upsert_partner_profile_updates_existing_row():
    row = WmsPartner(
        partner_id="northstar",
        display_name="Old",
        profile_json={"notes": "a"},
        branding_json={"logo_url": "https://example.com/logo.png"},
    )
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=row)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    out = await upsert_partner_profile(
        db,
        "northstar",
        {"notes": "b", "carriers": ["UPS"]},
        {"primary_color": "#0C757F", "branding_mode": "white_label"},
    )
    assert out["notes"] == "b"
    assert out["branding"]["branding_mode"] == "white_label"
    assert row.display_name == "Old"


@patch("app.routers.partners.get_reporting_summary", new_callable=AsyncMock)
@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_get_partner_account_success(_rls: AsyncMock, mock_summary: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    org = Organization(
        id=ORG_ID,
        name="Harbor Freight Desk",
        slug="harbor-freight",
        partner_id="northstar",
        settings_json={"client_onboarding": {"completed_at": "2026-01-01T00:00:00+00:00"}},
    )
    mock_summary.return_value = ReportingSummary(
        discrepancy_count=2,
        total_overcharge_minor=500,
        open_disputes=1,
        recovered_total_minor=100,
        fee_total_minor=20,
        compliance_rate=0.9,
        compliance_rate_note="ok",
        import_job_count=3,
    )
    session.scalar = AsyncMock(return_value=org)
    res = client.get(f"{PREFIX}/partners/northstar/accounts/{ORG_ID}")
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["discrepancy_count"] == 2
    assert body["profile"]["name"] == "Harbor Freight Desk"


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_create_partner_account_and_slug_fallback(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    new_id = uuid.uuid4()
    collision = Organization(id=uuid.uuid4(), name="x", slug="harbor-freight-desk", partner_id="northstar")

    def _add(obj):
        if isinstance(obj, Organization):
            obj.id = new_id
            obj.created_at = datetime.now(UTC)

    session.add = MagicMock(side_effect=_add)
    session.scalar = AsyncMock(return_value=collision)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    res = client.post(f"{PREFIX}/partners/northstar/accounts", json={"name": "Harbor Freight Desk!!!"})
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Harbor Freight Desk!!!"
    assert body["setup_complete"] is False
    assert body["slug"].startswith("harbor-freight-desk")
    assert len(body["slug"]) > len("harbor-freight-desk")


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_create_partner_account_rejects_empty_name(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _session = api_client
    res = client.post(f"{PREFIX}/partners/northstar/accounts", json={"name": "   "})
    assert res.status_code == 400


@patch("app.routers.partners.get_partner_profile", new_callable=AsyncMock)
def test_read_partner_profile(mock_get: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _session = api_client
    mock_get.return_value = {
        "partner_id": "northstar",
        "display_name": "Northstar WMS",
        "branding": {"branding_mode": "white_label"},
    }
    res = client.get(f"{PREFIX}/partners/northstar/profile")
    assert res.status_code == 200
    assert res.json()["display_name"] == "Northstar WMS"


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_public_branding_default_color(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    session.scalar = AsyncMock(return_value=None)
    with patch(
        "app.routers.partners.get_partner_profile",
        new_callable=AsyncMock,
        return_value={},
    ):
        res = client.get(f"{PREFIX}/partners/northstar/public-branding")
    assert res.status_code == 200
    body = res.json()
    assert body["display_name"] == "northstar"
    assert body["primary_color"] == "#059669"


@patch("app.services.partner_profiles.upsert_partner_profile", new_callable=AsyncMock)
@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_save_partner_onboarding(_rls: AsyncMock, mock_upsert: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _session = api_client
    mock_upsert.return_value = {"partner_id": "northstar", "ingest_mode": "file_drop"}
    res = client.put(
        f"{PREFIX}/partners/northstar/onboarding",
        headers=ORG_HEADER,
        json={"ingest_mode": "file_drop", "branding_mode": "white_label"},
    )
    assert res.status_code == 200
    assert res.json()["ingest_mode"] == "file_drop"


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_get_client_onboarding(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    org = Organization(
        id=ORG_ID,
        name="o",
        slug="o",
        partner_id="northstar",
        settings_json={"client_onboarding": {"org_name": "Acme", "carriers": ["UPS"]}},
    )
    session.scalar = AsyncMock(return_value=org)
    res = client.get(f"{PREFIX}/organizations/{ORG_ID}/client-onboarding", headers=ORG_HEADER)
    assert res.status_code == 200
    assert res.json()["org_name"] == "Acme"


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_get_client_onboarding_forbidden_mismatch(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _session = api_client
    other = uuid.uuid4()
    res = client.get(f"{PREFIX}/organizations/{other}/client-onboarding", headers=ORG_HEADER)
    assert res.status_code == 403
