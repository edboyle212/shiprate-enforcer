"""HTTP route coverage with mocked DB and services."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.models import (
    Discrepancy,
    DiscrepancyReviewStatus,
    DisputeCase,
    DisputeCaseStatus,
    ImportJob,
    ImportJobStatus,
    RateCardVersion,
    RateCardVersionStatus,
    SourceFileKind,
)
from app.services.compliance import ComplianceRunResult
from app.services.matching import MatchingRunResult
from tests.conftest import ORG_HEADER, ORG_ID

PREFIX = settings.api_prefix.rstrip("/")


def test_health_ok(api_client: tuple[TestClient, AsyncMock]):
    client, _ = api_client
    res = client.get(f"{PREFIX}/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_imports_missing_org_returns_401(api_client: tuple[TestClient, AsyncMock]):
    client, _ = api_client
    client.headers.pop("Authorization", None)
    client.headers.pop("X-Organization-Id", None)
    res = client.post(f"{PREFIX}/import-jobs?source_file_id={uuid.uuid4()}&idempotency_key=k")
    assert res.status_code == 401


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
@patch("app.routers.imports.storage_service")
def test_upload_source_file_empty(
    mock_storage: MagicMock,
    _rls: AsyncMock,
    api_client: tuple[TestClient, AsyncMock],
):
    client, _ = api_client
    res = client.post(
        f"{PREFIX}/source-files?kind=shipment_export",
        headers=ORG_HEADER,
        files={"file": ("a.csv", b"", "text/csv")},
    )
    assert res.status_code == 400


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
@patch("app.routers.imports.storage_service")
def test_upload_source_file_new(
    mock_storage: MagicMock,
    _rls: AsyncMock,
    api_client: tuple[TestClient, AsyncMock],
):
    client, session = api_client
    mock_storage.put_immutable.return_value = ("key/1", "abc123")
    mock_storage.backend_name = "filesystem"
    session.scalar = AsyncMock(return_value=None)
    session.commit = AsyncMock()

    def _refresh(record):
        record.id = uuid.uuid4()
        record.kind = SourceFileKind.shipment_export
        record.original_filename = "ship.csv"
        record.sha256_hex = "abc123"
        record.storage_backend = "filesystem"
        record.byte_size = 10

    session.refresh = AsyncMock(side_effect=_refresh)

    res = client.post(
        f"{PREFIX}/source-files?kind=shipment_export",
        headers=ORG_HEADER,
        files={"file": ("ship.csv", b"tracking\n1Z", "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["sha256_hex"] == "abc123"
    session.add.assert_called()


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_create_import_job_idempotent(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    sf_id = uuid.uuid4()
    job = ImportJob(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        source_file_id=sf_id,
        idempotency_key="idem-1",
        sha256_hex="dead",
        status=ImportJobStatus.pending,
    )
    session.scalar = AsyncMock(return_value=job)
    res = client.post(
        f"{PREFIX}/import-jobs?source_file_id={sf_id}&idempotency_key=idem-1",
        headers=ORG_HEADER,
    )
    assert res.status_code == 200
    assert res.json()["id"] == str(job.id)


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_create_import_job_missing_source(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    session.scalar = AsyncMock(side_effect=[None, None])
    res = client.post(
        f"{PREFIX}/import-jobs?source_file_id={uuid.uuid4()}&idempotency_key=x",
        headers=ORG_HEADER,
    )
    assert res.status_code == 404


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_map_csv_shipments(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    job_id = uuid.uuid4()
    job = ImportJob(
        id=job_id,
        organization_id=ORG_ID,
        source_file_id=uuid.uuid4(),
        idempotency_key="k",
        sha256_hex="x",
        status=ImportJobStatus.pending,
    )
    session.scalar = AsyncMock(return_value=job)
    session.commit = AsyncMock()
    res = client.post(
        f"{PREFIX}/imports/map-csv",
        headers=ORG_HEADER,
        json={
            "import_job_id": str(job_id),
            "csv_text": "tracking_number,carrier,service,dest_postal,weight_oz\n1Z999,UPS,GND,90210,16\n",
        },
    )
    assert res.status_code == 200
    assert res.json()["shipments_created"] == 1


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_map_invoice_csv_major_units(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    job_id = uuid.uuid4()
    job = ImportJob(
        id=job_id,
        organization_id=ORG_ID,
        source_file_id=uuid.uuid4(),
        idempotency_key="k",
        sha256_hex="x",
        status=ImportJobStatus.pending,
    )
    session.scalar = AsyncMock(return_value=job)
    session.commit = AsyncMock()
    res = client.post(
        f"{PREFIX}/imports/map-invoice-csv",
        headers=ORG_HEADER,
        json={
            "import_job_id": str(job_id),
            "csv_text": "tracking_number,charge_code,description,billed_amount\n1Z,TRANS,Freight,12.50\n",
            "amount_in_major_units": True,
        },
    )
    assert res.status_code == 200
    assert res.json()["invoice_lines_created"] == 1


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_create_and_approve_rate_card(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()

    session.refresh.side_effect = _refresh
    res = client.post(
        f"{PREFIX}/rate-cards",
        headers=ORG_HEADER,
        json={"carrier_code": "UPS", "version_label": "v1", "rules_json": {}},
    )
    assert res.status_code == 200
    rc_id = res.json()["id"]

    rc = RateCardVersion(
        id=uuid.UUID(rc_id),
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json={},
        status=RateCardVersionStatus.draft,
    )
    session.scalar = AsyncMock(return_value=rc)
    res2 = client.post(f"{PREFIX}/rate-cards/{rc_id}/approve", headers=ORG_HEADER)
    assert res2.status_code == 200
    assert res2.json()["status"] == "approved"


@patch("app.routers.rating.set_rls_organization", new_callable=AsyncMock)
def test_rating_run_requires_approved_card(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    rc_id = uuid.uuid4()
    rc = RateCardVersion(
        id=rc_id,
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json={},
        status=RateCardVersionStatus.draft,
    )
    session.scalar = AsyncMock(return_value=rc)
    res = client.post(
        f"{PREFIX}/rating-runs",
        headers=ORG_HEADER,
        json={"rate_card_version_id": str(rc_id), "shipments": []},
    )
    assert res.status_code == 400


@patch("app.routers.rating.set_rls_organization", new_callable=AsyncMock)
def test_rating_run_success(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    from tests.conftest import load_json_fixture

    rc_id = uuid.uuid4()
    rules = load_json_fixture("golden_rating_request.json").get("rate_card_snapshot") or {}
    rc = RateCardVersion(
        id=rc_id,
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json=rules,
        status=RateCardVersionStatus.approved,
    )
    session.scalar = AsyncMock(return_value=rc)
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    def _refresh(run):
        if not getattr(run, "id", None):
            run.id = uuid.uuid4()
        run.status = run.status

    session.refresh = AsyncMock(side_effect=_refresh)

    shipment = load_json_fixture("golden_rating_request.json")
    res = client.post(
        f"{PREFIX}/rating-runs",
        headers=ORG_HEADER,
        json={"rate_card_version_id": str(rc_id), "shipments": [shipment]},
    )
    assert res.status_code == 200
    assert res.json()["allowed_total_minor"] > 0


@patch("app.routers.compliance.run_compliance_for_matches", new_callable=AsyncMock)
@patch("app.routers.compliance.set_rls_organization", new_callable=AsyncMock)
def test_compliance_run_route(
    _rls: AsyncMock,
    mock_run: AsyncMock,
    api_client: tuple[TestClient, AsyncMock],
):
    client, session = api_client
    mock_run.return_value = ComplianceRunResult(checks_created=2, passed=1, discrepancies_created=1)
    session.commit = AsyncMock()
    res = client.post(f"{PREFIX}/compliance/run", headers=ORG_HEADER, json={})
    assert res.status_code == 200
    assert res.json()["checks_created"] == 2


@patch("app.routers.compliance.set_rls_organization", new_callable=AsyncMock)
def test_list_discrepancies(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    disc = Discrepancy(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        compliance_check_id=uuid.uuid4(),
        billed_amount_minor=1000,
        allowed_amount_minor=500,
        variance_minor=500,
        currency_code="USD",
        reason_codes=["OVER_TOLERANCE"],
        review_status=DiscrepancyReviewStatus.open,
        created_at=datetime.now(UTC),
    )
    session.scalars = AsyncMock(return_value=MagicMock(all=lambda: [disc]))
    res = client.get(f"{PREFIX}/discrepancies", headers=ORG_HEADER)
    assert res.status_code == 200
    assert len(res.json()) == 1


@patch("app.routers.matching.run_compliance_for_matches", new_callable=AsyncMock)
@patch("app.routers.matching.run_automatic_matching", new_callable=AsyncMock)
@patch("app.routers.matching.set_rls_organization", new_callable=AsyncMock)
def test_matching_run_with_compliance(
    _rls: AsyncMock,
    mock_match: AsyncMock,
    mock_comp: AsyncMock,
    api_client: tuple[TestClient, AsyncMock],
):
    client, session = api_client
    mock_match.return_value = MatchingRunResult(1, 0, 0)
    mock_comp.return_value = ComplianceRunResult(1, 1, 0)
    session.commit = AsyncMock()
    res = client.post(f"{PREFIX}/matching/run", headers=ORG_HEADER, json={"run_compliance": True})
    assert res.status_code == 200
    assert res.json()["exact_matches"] == 1


@patch("app.routers.matching.create_manual_match", new_callable=AsyncMock)
@patch("app.routers.matching.set_rls_organization", new_callable=AsyncMock)
def test_manual_match_not_found(
    _rls: AsyncMock,
    mock_create: AsyncMock,
    api_client: tuple[TestClient, AsyncMock],
):
    client, session = api_client
    mock_create.side_effect = ValueError("Shipment or invoice line not found for organization")
    session.commit = AsyncMock()
    res = client.post(
        f"{PREFIX}/matching/manual-link",
        headers=ORG_HEADER,
        json={"shipment_id": str(uuid.uuid4()), "carrier_invoice_line_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


@patch("app.routers.etl.poll_etl_drop", new_callable=AsyncMock)
def test_etl_poll_drop(mock_poll: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _ = api_client
    mock_poll.return_value = {"partner_id": "jasci", "ingested": ["a.csv"], "skipped": []}
    res = client.post(f"{PREFIX}/etl/poll-drop", headers=ORG_HEADER)
    assert res.status_code == 200
    assert res.json()["ingested"] == ["a.csv"]


@patch("app.routers.ai.map_columns", new_callable=AsyncMock)
@patch("app.routers.ai.set_rls_organization", new_callable=AsyncMock)
def test_ai_map_columns_route(_rls: AsyncMock, mock_map: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    from app.services.ai_mapping import MapColumnsResult

    client, session = api_client
    rid = uuid.uuid4()
    mock_map.return_value = MapColumnsResult(mapping={"tracking_number": "track"}, used_ai=False, provider=None, request_id=rid)
    session.commit = AsyncMock()
    res = client.post(
        f"{PREFIX}/ai/map-columns",
        headers=ORG_HEADER,
        json={"headers": ["track"], "kind": "shipment_export"},
    )
    assert res.status_code == 200
    assert res.json()["used_ai"] is False


@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
@patch("app.routers.disputes.outbound_mail_configured", return_value=True)
@patch("app.routers.disputes.outbound_mail_from_address", return_value="d@example.com")
def test_dispute_outbound_mail(_mail: MagicMock, _from: MagicMock, _rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _ = api_client
    res = client.get(f"{PREFIX}/dispute-cases/outbound-mail", headers=ORG_HEADER)
    assert res.status_code == 200
    assert res.json()["configured"] is True


@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_list_dispute_cases(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    case = DisputeCase(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        discrepancy_id=uuid.uuid4(),
        claim_amount_minor=500,
        currency_code="USD",
        status=DisputeCaseStatus.open,
        autonomy_tier="draft",
        fee_bps=2000,
        created_at=datetime.now(UTC),
    )
    session.scalars = AsyncMock(return_value=MagicMock(all=lambda: [case]))
    res = client.get(f"{PREFIX}/dispute-cases", headers=ORG_HEADER)
    assert res.status_code == 200
    assert res.json()[0]["claim_amount_minor"] == 500


@patch("app.routers.disputes.negotiation_service.run_negotiation_step", new_callable=AsyncMock)
@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_negotiate_mail_failure(_rls: AsyncMock, mock_neg: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    mock_neg.side_effect = ValueError("mail_delivery_failed")
    session.commit = AsyncMock()
    res = client.post(f"{PREFIX}/dispute-cases/{uuid.uuid4()}/negotiate", headers=ORG_HEADER)
    assert res.status_code == 502


@patch("app.routers.orgs.set_rls_organization", new_callable=AsyncMock)
def test_create_organization(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    session.scalar = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    def _refresh(org):
        org.id = ORG_ID

    session.refresh.side_effect = _refresh
    res = client.post(f"{PREFIX}/organizations", json={"name": "Acme", "slug": "acme-test-unique"})
    assert res.status_code == 200
    assert res.json()["slug"] == "acme-test-unique"


def test_get_current_org_missing_context(api_client: tuple[TestClient, AsyncMock]):
    client, _ = api_client
    client.headers.pop("Authorization", None)
    client.headers.pop("X-Organization-Id", None)
    res = client.get(f"{PREFIX}/organizations/current")
    assert res.status_code == 401
