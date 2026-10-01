"""Negotiation tiers, send gates, platform pause, and fee math."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models import (
    Discrepancy,
    DisputeCase,
    DisputeCaseStatus,
    DisputeMessage,
    DisputeMessageDirection,
    DisputeMessageStatus,
)
from app.services.mail import LogMailSender
from app.services.negotiation import (
    apply_credit,
    apply_negotiation_step,
    classify_carrier_reply,
    fee_amount_minor,
    should_send_outbound,
)
from app.services.org_settings import apply_platform_recovery_fee, merge_client_settings

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")


@pytest.fixture(autouse=True)
def _enable_outbound_carrier_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "outbound_carrier_send_enabled", True)
    monkeypatch.setattr(
        "app.services.negotiation.outbound_mail_configured",
        lambda: True,
    )


def _discrepancy() -> Discrepancy:
    return Discrepancy(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        compliance_check_id=uuid.uuid4(),
        billed_amount_minor=1500,
        allowed_amount_minor=1000,
        variance_minor=500,
        currency_code="USD",
        reason_codes=["OVER_TOLERANCE"],
        trace_summary_json={"carrier_code": "UPS", "zone": "3", "engine_version": "0.1.0"},
    )


def _case(*, autonomy_tier: str, fee_bps: int = 2000) -> DisputeCase:
    disc = _discrepancy()
    case = DisputeCase(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        discrepancy_id=disc.id,
        claim_amount_minor=500,
        currency_code="USD",
        status=DisputeCaseStatus.open,
        autonomy_tier=autonomy_tier,
        fee_bps=fee_bps,
    )
    case.discrepancy = disc
    case.events = []
    case.drafts = []
    case.messages = []
    case.created_at = datetime.now(UTC)
    return case


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()  # type: ignore[attr-defined]


def test_fee_amount_is_integer_bps():
    assert fee_amount_minor(recovered_amount_minor=500, fee_bps=2000) == 100
    assert fee_amount_minor(recovered_amount_minor=1, fee_bps=2000) == 0


def test_client_patch_cannot_change_recovery_fee():
    current = {"recovery_fee_bps": 2000, "autonomy_tier": "draft"}
    merged = merge_client_settings(current, {"autonomy_tier": "autonomous", "recovery_fee_bps": 1})
    assert merged["autonomy_tier"] == "draft"
    assert merged["recovery_fee_bps"] == 2000


def test_platform_can_set_recovery_fee():
    merged = apply_platform_recovery_fee({"autonomy_tier": "draft"}, 1500)
    assert merged["recovery_fee_bps"] == 1500


@pytest.mark.asyncio
async def test_draft_tier_never_sends():
    assert should_send_outbound("draft") is False
    session = _Session()
    sender = LogMailSender()
    case = _case(autonomy_tier="draft")
    await apply_negotiation_step(session, case, org_settings={}, sender=sender)
    assert sender.sent == []
    assert case.messages[0].status == DisputeMessageStatus.draft
    assert case.status == DisputeCaseStatus.awaiting_approval


@pytest.mark.asyncio
async def test_approve_each_sends_only_after_approve():
    session = _Session()
    sender = LogMailSender()
    case = _case(autonomy_tier="approve_each")
    await apply_negotiation_step(session, case, org_settings={}, sender=sender)
    assert sender.sent == []
    assert case.messages[0].status == DisputeMessageStatus.draft

    from app.services.negotiation import approve_and_send

    async def _scalar(_stmt):
        text = str(_stmt)
        if "organizations" in text.lower():
            return SimpleNamespace(settings_json={})
        return case

    session.scalar = _scalar  # type: ignore[attr-defined]
    await approve_and_send(
        session,
        organization_id=ORG_ID,
        dispute_case_id=case.id,
        sender=sender,
    )
    assert len(sender.sent) == 1
    assert case.messages[0].status == DisputeMessageStatus.sent
    assert case.status == DisputeCaseStatus.awaiting_carrier


@pytest.mark.asyncio
async def test_draft_tier_can_mark_sent_manually():
    session = _Session()
    sender = LogMailSender()
    case = _case(autonomy_tier="draft")
    await apply_negotiation_step(session, case, org_settings={}, sender=sender)
    assert sender.sent == []

    from app.services.negotiation import approve_and_send

    async def _scalar(_stmt):
        text = str(_stmt)
        if "organizations" in text.lower():
            return SimpleNamespace(settings_json={})
        return case

    session.scalar = _scalar  # type: ignore[attr-defined]
    await approve_and_send(
        session,
        organization_id=ORG_ID,
        dispute_case_id=case.id,
        sender=sender,
    )
    assert len(sender.sent) == 1
    assert case.messages[0].status == DisputeMessageStatus.sent
    assert case.status == DisputeCaseStatus.awaiting_carrier


@pytest.mark.asyncio
async def test_autonomous_sends_first_ask():
    session = _Session()
    sender = LogMailSender()
    case = _case(autonomy_tier="autonomous")
    await apply_negotiation_step(session, case, org_settings={}, sender=sender)
    assert len(sender.sent) == 1
    assert case.messages[0].status == DisputeMessageStatus.sent
    assert case.status == DisputeCaseStatus.awaiting_carrier


@pytest.mark.asyncio
async def test_partial_credit_pauses_for_platform():
    session = _Session()
    sender = LogMailSender()
    case = _case(autonomy_tier="autonomous")
    await apply_negotiation_step(session, case, org_settings={}, sender=sender)
    inbound = DisputeMessage(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        dispute_case_id=case.id,
        direction=DisputeMessageDirection.inbound,
        email_subject="offer",
        email_body="partial",
        status=DisputeMessageStatus.sent,
        round_number=1,
        offered_amount_minor=200,
        denied=False,
        created_at=datetime.now(UTC),
    )
    case.messages.append(inbound)
    await apply_negotiation_step(session, case, org_settings={}, sender=sender)
    assert case.status == DisputeCaseStatus.awaiting_platform
    assert case.recovered_amount_minor is None


def test_record_credit_requires_fee():
    case = _case(autonomy_tier="draft")
    apply_credit(case, recovered_amount_minor=200)
    assert case.recovered_amount_minor == 200
    assert case.fee_amount_minor == 40
    assert case.status == DisputeCaseStatus.credited


def test_classify_full_vs_partial():
    assert classify_carrier_reply(denied=False, offered_amount_minor=500, claim_amount_minor=500) == "full_credit"
    assert classify_carrier_reply(denied=False, offered_amount_minor=100, claim_amount_minor=500) == "platform"
    assert classify_carrier_reply(denied=True, offered_amount_minor=None, claim_amount_minor=500) == "platform"


@pytest.fixture
def api_client():
    from app.db import get_db
    from app.main import app

    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("app.routers.orgs.set_rls_organization", new_callable=AsyncMock)
def test_client_patch_route_strips_fee(mock_rls: AsyncMock, api_client: TestClient):
    from app.models import Organization

    org = Organization(id=ORG_ID, name="Acme", slug="acme", settings_json={"recovery_fee_bps": 2000})

    async def _scalar(_stmt):
        return org

    session = AsyncMock()
    session.scalar = _scalar

    async def _db():
        yield session

    from app.db import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _db
    prefix = settings.api_prefix.rstrip("/")
    from tests.db import admin_auth_headers

    response = api_client.patch(
            f"{prefix}/organizations/current",
            headers=admin_auth_headers(),
            json={"autonomy_tier": "approve_each", "recovery_fee_bps": 1},
        )
    assert response.status_code == 200
    assert response.json()["settings_json"]["recovery_fee_bps"] == 2000
    assert response.json()["settings_json"].get("autonomy_tier", "draft") == "draft"
    app.dependency_overrides.clear()
