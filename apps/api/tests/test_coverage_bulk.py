"""Targeted coverage for remaining gaps."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.middleware.tenancy import TenancyMiddleware
from app.models import (
    DisputeCase,
    DisputeCaseStatus,
    DisputeMessage,
    DisputeMessageDirection,
    DisputeMessageStatus,
    MatchType,
    ShipmentInvoiceMatch,
    WmsPartner,
)
from app.services import import_jobs as import_jobs_service
from app.services.compliance import list_discrepancies, run_compliance_for_invoice_line
from app.services.matching import get_match_for_invoice_line, persist_tracking_match
from tests.conftest import ORG_HEADER, ORG_ID
from tests.db import admin_auth_headers

PREFIX = settings.api_prefix.rstrip("/")


def _sync_local(session: MagicMock):
    outer = MagicMock()
    outer.__enter__.return_value = session
    outer.__exit__.return_value = None
    session.begin.return_value = outer
    return outer


def test_import_jobs_creates_new_job():
    session = MagicMock()
    session.get.return_value = None
    session.scalar.side_effect = [None, None]
    local = _sync_local(session)

    def _refresh(job):
        job.id = uuid.uuid4()

    session.refresh.side_effect = _refresh

    with patch.object(import_jobs_service, "SessionLocal", return_value=local):
        job = import_jobs_service.create_import_job(
            organization_id=ORG_ID,
            idempotency_key="new-key",
            source_file_sha256="sha" * 8,
            kind="shipment_export",
        )
    assert job.id is not None
    session.add.assert_called()


@patch("app.services.matching._sync_session_factory")
def test_persist_tracking_match_creates(mock_factory: MagicMock):
    session = MagicMock()
    session.get.return_value = None
    session.scalar.return_value = None
    local = _sync_local(session)
    mock_factory.return_value = MagicMock(return_value=local)

    match = persist_tracking_match(
        organization_id=ORG_ID,
        shipment_id=uuid.uuid4(),
        carrier_invoice_line_id=uuid.uuid4(),
        shipment_tracking="1Z",
        invoice_tracking="1Z",
    )
    assert match.match_type == MatchType.exact


@patch("app.services.compliance._sync_session_factory")
def test_run_compliance_for_invoice_line_persists(mock_factory: MagicMock):
    session = MagicMock()
    session.get.return_value = None
    session.scalar.return_value = None
    local = _sync_local(session)
    mock_factory.return_value = MagicMock(return_value=local)
    line_id = uuid.uuid4()
    result = run_compliance_for_invoice_line(
        organization_id=ORG_ID,
        carrier_invoice_line_id=line_id,
        rating_run_id=uuid.uuid4(),
        billed_amount_minor=20_000,
        allowed_amount_minor=10_000,
    )
    assert result is not None
    assert result.variance_minor == 10_000


@patch("app.services.compliance._sync_session_factory")
def test_list_discrepancies_sync(mock_factory: MagicMock):
    session = MagicMock()
    disc_id = uuid.uuid4()
    line_id = uuid.uuid4()
    disc = MagicMock(
        id=disc_id,
        reason_codes=["BILLED_EXCEEDS_ALLOWED"],
        billed_amount_minor=100,
        allowed_amount_minor=50,
        variance_minor=50,
    )
    match = MagicMock(carrier_invoice_line_id=line_id)
    session.execute.return_value.all.return_value = [(disc, MagicMock(), match)]
    local = _sync_local(session)
    mock_factory.return_value = MagicMock(return_value=local)
    rows = list_discrepancies(organization_id=ORG_ID, carrier_invoice_line_id=line_id)
    assert rows[0].id == disc_id


@pytest.mark.asyncio
async def test_tenancy_middleware_clerk_stub(monkeypatch: pytest.MonkeyPatch):
    from starlette.requests import Request
    from starlette.responses import Response

    monkeypatch.setattr("app.middleware.tenancy.settings.clerk_secret_key", "sk_test")
    middleware = TenancyMiddleware(app=MagicMock())

    async def call_next(request):
        return Response("ok")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (b"authorization", b"Bearer token"),
            (b"x-clerk-org-id", str(ORG_ID).encode()),
        ],
    }
    response = await middleware.dispatch(Request(scope), call_next)
    assert response.headers.get("X-Organization-Id") == str(ORG_ID)


@patch("app.routers.disputes.negotiation_service.record_inbound_reply", new_callable=AsyncMock)
@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_post_carrier_reply(_rls: AsyncMock, mock_reply: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    msg = DisputeMessage(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=uuid.uuid4(),
        direction=DisputeMessageDirection.inbound,
        email_subject="s",
        email_body="b",
        status=DisputeMessageStatus.sent,
        round_number=1,
        created_at=datetime.now(UTC),
    )
    mock_reply.return_value = msg
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    res = client.post(
        f"{PREFIX}/dispute-cases/{uuid.uuid4()}/replies",
        headers={**ORG_HEADER, **admin_auth_headers()},
        json={"subject": "s", "body": "b"},
    )
    assert res.status_code == 200


@patch("app.routers.disputes.negotiation_service.approve_and_send", new_callable=AsyncMock)
@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_approve_send(_rls: AsyncMock, mock_send: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    msg = DisputeMessage(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=uuid.uuid4(),
        direction=DisputeMessageDirection.outbound,
        email_subject="s",
        email_body="b",
        status=DisputeMessageStatus.sent,
        round_number=1,
        created_at=datetime.now(UTC),
        sent_at=datetime.now(UTC),
    )
    mock_send.return_value = msg
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    res = client.post(f"{PREFIX}/dispute-cases/{uuid.uuid4()}/approve-send", headers=ORG_HEADER, json={})
    assert res.status_code == 200


@patch("app.routers.disputes.negotiation_service.stop_case", new_callable=AsyncMock)
@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_stop_case(_rls: AsyncMock, mock_stop: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    case = DisputeCase(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        discrepancy_id=uuid.uuid4(),
        claim_amount_minor=100,
        currency_code="USD",
        status=DisputeCaseStatus.closed,
        autonomy_tier="draft",
        fee_bps=2000,
        created_at=datetime.now(UTC),
    )
    mock_stop.return_value = case
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    res = client.post(f"{PREFIX}/dispute-cases/{case.id}/stop", headers=ORG_HEADER)
    assert res.status_code == 200


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_partner_profile_put(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    row = WmsPartner(partner_id="jasci", display_name="J", profile_json={}, branding_json={})
    session.scalar = AsyncMock(return_value=row)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    res = client.put(
        f"{PREFIX}/partners/jasci/profile",
        headers={**ORG_HEADER, **admin_auth_headers()},
        json={"partner_name": "Jasci", "notes": "hi"},
    )
    assert res.status_code == 200


@patch("app.services.matching._sync_session_factory")
def test_get_match_for_invoice_line(mock_factory: MagicMock):
    session = MagicMock()
    existing = ShipmentInvoiceMatch(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        shipment_id=uuid.uuid4(),
        carrier_invoice_line_id=uuid.uuid4(),
        match_type=MatchType.manual,
    )
    session.scalar.return_value = existing
    local = _sync_local(session)
    mock_factory.return_value = MagicMock(return_value=local)
    found = get_match_for_invoice_line(organization_id=ORG_ID, carrier_invoice_line_id=uuid.uuid4())
    assert found.id == existing.id
