"""Dashboard reporting summary endpoint returns expected KPI keys."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.reporting import ReportingSummary

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")

REQUIRED_SUMMARY_KEYS = frozenset(
    {
        "discrepancy_count",
        "total_overcharge_minor",
        "open_disputes",
        "recovered_total_minor",
        "fee_total_minor",
        "import_job_count",
        "compliance_rate",
        "compliance_rate_note",
    }
)


@pytest.fixture
def api_client():
    from app.db import get_db
    from app.main import app

    async def _fake_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("app.routers.reporting.set_rls_organization", new_callable=AsyncMock)
@patch("app.routers.reporting.get_reporting_summary", new_callable=AsyncMock)
def test_reporting_summary_returns_expected_keys(
    mock_get_summary: AsyncMock,
    _mock_rls: AsyncMock,
    api_client: TestClient,
):
    mock_get_summary.return_value = ReportingSummary(
        discrepancy_count=3,
        total_overcharge_minor=12_50,
        open_disputes=1,
        recovered_total_minor=500,
        fee_total_minor=100,
        import_job_count=2,
        compliance_rate=0.875,
        compliance_rate_note=None,
    )

    prefix = settings.api_prefix.rstrip("/")
    response = api_client.get(
        f"{prefix}/reporting/summary",
        headers={"X-Organization-Id": str(ORG_ID)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert REQUIRED_SUMMARY_KEYS <= set(payload.keys())
    assert payload["discrepancy_count"] == 3
    assert payload["total_overcharge_minor"] == 1250
    assert payload["open_disputes"] == 1
    assert payload["compliance_rate"] == 0.875
