"""Client organization profile GET/PATCH."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models import Organization
from app.services.org_settings import apply_profile_patch, profile_from_org

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")


def test_apply_profile_patch_updates_name_tolerances_autonomy_leaves_fee():
    org = Organization(
        id=ORG_ID,
        name="Old Co",
        slug="old-co",
        partner_id="jasci",
        settings_json={
            "recovery_fee_bps": 2000,
            "autonomy_tier": "draft",
            "client_onboarding": {"carriers": ["UPS"], "tolerances": {"absolute_minor": 500, "percent": 2}},
        },
    )
    apply_profile_patch(
        org,
        {
            "name": "New Co",
            "contacts": {
                "primary_name": "Pat",
                "primary_email": "pat@new.co",
                "billing_email": "ap@new.co",
                "disputes_email": "claims@new.co",
            },
            "people": [{"name": "Pat", "email": "pat@new.co", "role": "owner"}],
            "carriers": ["UPS", "FedEx"],
            "tolerances": {"absolute_minor": 250, "percent": 1.5},
            "autonomy_tier": "approve_each",
            "carrier_billing_emails": {"UPS": "ups-billing@new.co"},
            "recovery_fee_bps": 1,
        },
    )
    profile = profile_from_org(org)
    assert org.name == "New Co"
    assert profile["tolerances"]["absolute_minor"] == 250
    assert profile["tolerances"]["percent"] == 1.5
    assert profile["autonomy_tier"] == "draft"
    assert profile["recovery_fee_bps"] == 2000
    assert profile["carriers"] == ["UPS", "FedEx"]
    assert profile["contacts"]["primary_email"] == "pat@new.co"
    assert profile["people"][0]["role"] == "owner"


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
def test_profile_patch_route_strips_fee(mock_rls: AsyncMock, api_client: TestClient):
    from app.db import get_db
    from app.main import app
    from app.routers import orgs as orgs_router

    org = Organization(
        id=ORG_ID,
        name="Acme",
        slug="acme",
        settings_json={"recovery_fee_bps": 2000, "autonomy_tier": "draft"},
    )

    async def _scalar(_stmt):
        return org

    session = AsyncMock()
    session.scalar = _scalar

    async def _db():
        yield session

    app.dependency_overrides[get_db] = _db
    prefix = settings.api_prefix.rstrip("/")
    from tests.db import admin_auth_headers

    response = api_client.patch(
            f"{prefix}/organizations/current/profile",
            headers=admin_auth_headers(),
            json={
                "name": "Acme Logistics",
                "tolerances": {"absolute_minor": 100, "percent": 3},
                "autonomy_tier": "approve_each",
                "recovery_fee_bps": 1,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Logistics"
    assert body["tolerances"]["absolute_minor"] == 100
    assert body["autonomy_tier"] == "draft"
    assert body["recovery_fee_bps"] == 2000
    app.dependency_overrides.clear()


@patch("app.routers.orgs.set_rls_organization", new_callable=AsyncMock)
def test_profile_get_includes_setup_complete(_mock_rls: AsyncMock, api_client: TestClient):
    from app.db import get_db
    from app.main import app
    from app.routers import orgs as orgs_router

    org = Organization(
        id=ORG_ID,
        name="Acme",
        slug="acme",
        partner_id="jasci",
        settings_json={
            "client_onboarding": {"completed_at": datetime.now(UTC).isoformat()},
        },
        created_at=datetime.now(UTC),
    )

    async def _scalar(_stmt):
        return org

    session = AsyncMock()
    session.scalar = _scalar

    async def _db():
        yield session

    app.dependency_overrides[get_db] = _db
    prefix = settings.api_prefix.rstrip("/")
    from tests.db import admin_auth_headers

    response = api_client.get(
            f"{prefix}/organizations/current/profile",
            headers=admin_auth_headers(),
        )
    assert response.status_code == 200
    assert response.json()["setup_complete"] is True
    app.dependency_overrides.clear()
