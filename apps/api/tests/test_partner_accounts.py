"""Publisher partner account list, create, and isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models import Organization

ORG_A = uuid.UUID("01950000-0000-7000-8000-00000000000a")
ORG_B = uuid.UUID("01950000-0000-7000-8000-00000000000b")


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


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
def test_partner_account_list_only_that_partner(_mock_rls: AsyncMock, api_client: TestClient):
    from app.db import get_db
    from app.main import app

    jasci = Organization(
        id=ORG_A,
        name="Warehouse A",
        slug="warehouse-a",
        partner_id="jasci",
        settings_json={"client_onboarding": {"completed_at": "2026-01-01T00:00:00+00:00"}},
        created_at=datetime.now(UTC),
    )
    other = Organization(
        id=ORG_B,
        name="Other",
        slug="other",
        partner_id="other-wms",
        settings_json={},
        created_at=datetime.now(UTC),
    )

    async def _scalars(_stmt):
        return SimpleNamespace(all=lambda: [jasci])

    session = AsyncMock()
    session.scalars = _scalars

    async def _db():
        yield session

    app.dependency_overrides[get_db] = _db
    prefix = settings.api_prefix.rstrip("/")
    response = api_client.get(f"{prefix}/partners/jasci/accounts")
    assert response.status_code == 200
    rows = response.json()
    ids = {row["id"] for row in rows}
    assert str(ORG_A) in ids
    assert str(ORG_B) not in ids
    assert rows[0]["setup_complete"] is True
    assert rows[0]["name"] == "Warehouse A"
    app.dependency_overrides.clear()


@patch("app.routers.partners.set_rls_organization", new_callable=AsyncMock)
@patch("app.routers.partners.get_reporting_summary", new_callable=AsyncMock)
def test_partner_account_detail_404_for_other_partner(
    mock_summary: AsyncMock,
    _mock_rls: AsyncMock,
    api_client: TestClient,
):
    from app.db import get_db
    from app.main import app

    org = Organization(
        id=ORG_A,
        name="Warehouse A",
        slug="warehouse-a",
        partner_id="other-wms",
        settings_json={},
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
    response = api_client.get(f"{prefix}/partners/jasci/accounts/{ORG_A}")
    assert response.status_code == 404
    mock_summary.assert_not_called()
    app.dependency_overrides.clear()
