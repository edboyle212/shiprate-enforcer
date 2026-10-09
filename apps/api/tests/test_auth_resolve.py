"""Auth resolution (test tokens and dev header)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.auth.resolve import principal_from_bearer, principal_from_dev_header
from tests.db import ORG_ID

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_test_bearer_builds_principal_without_db():
    session = AsyncMock()
    token = f"Bearer shiprate-test:member-user:{ORG_ID}"
    principal = await principal_from_bearer(session, token)
    assert principal is not None
    assert principal.organization_id == ORG_ID
    assert principal.external_auth_id == "member-user"
    assert principal.membership_role == "owner"
    session.scalar.assert_not_called()


@pytest.mark.asyncio
async def test_test_bearer_platform_admin_flag():
    session = AsyncMock()
    token = f"Bearer shiprate-test:test-platform-admin:{ORG_ID}"
    principal = await principal_from_bearer(session, token)
    assert principal is not None
    assert principal.is_platform_admin is True
    assert "northstar" in principal.partner_ids


@pytest.mark.asyncio
async def test_dev_header_allowed_in_test_env():
    session = AsyncMock()
    principal = await principal_from_dev_header(session, str(ORG_ID), None)
    assert principal is not None
    assert principal.organization_id == ORG_ID


@pytest.mark.asyncio
async def test_invalid_bearer_returns_none():
    session = AsyncMock()
    assert await principal_from_bearer(session, "Bearer not-a-test-token") is None
    assert await principal_from_bearer(session, None) is None


@pytest.mark.asyncio
async def test_malformed_test_token_returns_none():
    session = AsyncMock()
    assert await principal_from_bearer(session, "Bearer shiprate-test:only-two") is None
    bad_org = "Bearer shiprate-test:user:not-a-uuid"
    assert await principal_from_bearer(session, bad_org) is None
