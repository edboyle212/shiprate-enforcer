"""Additional router coverage for compliance, disputes, partners, orgs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.models import (
    ComplianceCheck,
    Discrepancy,
    DiscrepancyReviewStatus,
    DisputeCase,
    DisputeCaseStatus,
    DisputeDraft,
    DisputeDraftStatus,
    DisputeMessage,
    DisputeMessageDirection,
    DisputeMessageStatus,
    Organization,
    ShipmentInvoiceMatch,
    WmsPartner,
)
from tests.conftest import ORG_HEADER, ORG_ID

PREFIX = settings.api_prefix.rstrip("/")


@patch("app.services.partner_profiles.get_partner_profile", new_callable=AsyncMock)
@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_partner_onboarding_get(_rls: AsyncMock, mock_get: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, _ = api_client
    mock_get.return_value = {"partner_id": "jasci"}
    res = client.get(f"{PREFIX}/partners/jasci/onboarding", headers=ORG_HEADER)
    assert res.status_code == 200


@patch("app.routers.disputes.dispute_service.open_dispute_case", new_callable=AsyncMock)
@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_open_dispute_case_not_found(_rls: AsyncMock, mock_open: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    mock_open.side_effect = ValueError("discrepancy_not_found")
    session.commit = AsyncMock()
    res = client.post(f"{PREFIX}/discrepancies/{uuid.uuid4()}/open-case", headers=ORG_HEADER)
    assert res.status_code == 404


@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_get_dispute_case_detail(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    case_id = uuid.uuid4()
    case = DisputeCase(
        id=case_id,
        organization_id=ORG_ID,
        discrepancy_id=uuid.uuid4(),
        claim_amount_minor=100,
        currency_code="USD",
        status=DisputeCaseStatus.open,
        autonomy_tier="draft",
        fee_bps=2000,
        created_at=datetime.now(UTC),
    )
    draft = DisputeDraft(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=case_id,
        email_subject="s",
        email_body="b",
        status=DisputeDraftStatus.draft,
        created_at=datetime.now(UTC),
    )
    case.drafts = [draft]
    case.events = []
    msg = DisputeMessage(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=case_id,
        direction=DisputeMessageDirection.outbound,
        email_subject="s",
        email_body="b",
        status=DisputeMessageStatus.draft,
        round_number=1,
        created_at=datetime.now(UTC),
    )
    case.messages = [msg]
    session.scalar = AsyncMock(return_value=case)
    res = client.get(f"{PREFIX}/dispute-cases/{case_id}", headers=ORG_HEADER)
    assert res.status_code == 200
    assert res.json()["drafts"][0]["email_subject"] == "s"


@patch("app.routers.disputes.dispute_service.create_or_refresh_draft", new_callable=AsyncMock)
@patch("app.routers.disputes.set_rls_organization", new_callable=AsyncMock)
def test_create_dispute_draft_route(_rls: AsyncMock, mock_draft: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    draft = DisputeDraft(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=uuid.uuid4(),
        email_subject="s",
        email_body="b",
        status=DisputeDraftStatus.draft,
        created_at=datetime.now(UTC),
    )
    mock_draft.return_value = draft
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    res = client.post(f"{PREFIX}/dispute-cases/{uuid.uuid4()}/draft", headers=ORG_HEADER)
    assert res.status_code == 200


@patch("app.routers.compliance.set_rls_organization", new_callable=AsyncMock)
def test_get_discrepancy_detail(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    disc_id = uuid.uuid4()
    match_id = uuid.uuid4()
    check = ComplianceCheck(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        shipment_invoice_match_id=match_id,
        rate_card_version_id=uuid.uuid4(),
        billed_amount_minor=100,
        allowed_amount_minor=50,
        variance_minor=50,
        within_tolerance=False,
    )
    disc = Discrepancy(
        id=disc_id,
        organization_id=ORG_ID,
        compliance_check_id=check.id,
        billed_amount_minor=100,
        allowed_amount_minor=50,
        variance_minor=50,
        currency_code="USD",
        reason_codes=["X"],
        review_status=DiscrepancyReviewStatus.open,
        created_at=datetime.now(UTC),
        trace_summary_json={},
    )
    disc.compliance_check = check
    session.scalar = AsyncMock(return_value=disc)
    match = ShipmentInvoiceMatch(
        id=match_id,
        organization_id=ORG_ID,
        shipment_id=uuid.uuid4(),
        carrier_invoice_line_id=uuid.uuid4(),
        match_type="exact",
    )
    session.get = AsyncMock(return_value=match)
    res = client.get(f"{PREFIX}/discrepancies/{disc_id}", headers=ORG_HEADER)
    assert res.status_code == 200
    assert res.json()["shipment_id"] is not None


@patch("app.routers.compliance.set_rls_organization", new_callable=AsyncMock)
def test_review_discrepancy(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    disc_id = uuid.uuid4()
    disc = Discrepancy(
        id=disc_id,
        organization_id=ORG_ID,
        compliance_check_id=uuid.uuid4(),
        billed_amount_minor=100,
        allowed_amount_minor=50,
        variance_minor=50,
        currency_code="USD",
        reason_codes=["X"],
        review_status=DiscrepancyReviewStatus.open,
        created_at=datetime.now(UTC),
        trace_summary_json={},
    )
    disc.compliance_check = None
    session.scalar = AsyncMock(return_value=disc)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    res = client.patch(
        f"{PREFIX}/discrepancies/{disc_id}",
        headers=ORG_HEADER,
        json={"review_status": "approved", "review_comment": "looks good"},
    )
    assert res.status_code == 200
    assert res.json()["review_status"] == "approved"


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_partners_public_branding(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    partner = WmsPartner(
        partner_id="jasci",
        display_name="Jasci",
        profile_json={},
        branding_json={"primary_color": "#000"},
    )
    session.scalar = AsyncMock(return_value=partner)
    res = client.get(f"{PREFIX}/partners/jasci/public-branding")
    assert res.status_code == 200
    assert res.json()["display_name"] == "Jasci"


@patch("app.routers.orgs.set_rls_organization", new_callable=AsyncMock)
@patch("app.routers.orgs.get_organization_id", return_value=ORG_ID)
def test_recovery_fee_requires_admin(_org: MagicMock, _rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    org = Organization(id=ORG_ID, name="o", slug="o", settings_json={"recovery_fee_bps": 2000})
    session.scalar = AsyncMock(return_value=org)
    res = client.patch(f"{PREFIX}/organizations/current/recovery-fee", json={"recovery_fee_bps": 1500})
    assert res.status_code == 403


@patch("app.routers.imports.set_rls_organization", new_callable=AsyncMock)
def test_save_client_onboarding(_rls: AsyncMock, api_client: tuple[TestClient, AsyncMock]):
    client, session = api_client
    org = Organization(id=ORG_ID, name="o", slug="o", settings_json={})
    session.scalar = AsyncMock(return_value=org)
    session.commit = AsyncMock()
    res = client.put(
        f"{PREFIX}/organizations/{ORG_ID}/client-onboarding",
        headers=ORG_HEADER,
        json={"org_name": "Acme", "carriers": ["UPS"]},
    )
    assert res.status_code == 200
    assert res.json()["org_name"] == "Acme"
