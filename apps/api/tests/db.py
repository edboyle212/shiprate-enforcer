"""Database helpers for integration tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import (
    MembershipRole,
    Organization,
    OrganizationMembership,
    User,
)

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
TEST_USER_EXTERNAL = "test-user-001"
TEST_ADMIN_EXTERNAL = "test-platform-admin"


def admin_auth_headers(
    *,
    org_id: uuid.UUID = ORG_ID,
) -> dict[str, str]:
    return auth_headers(org_id=org_id, external_id=TEST_ADMIN_EXTERNAL)


def database_url() -> str:
    raw = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not raw:
        pytest.fail("TEST_DATABASE_URL or DATABASE_URL is required for integration tests")
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


def auth_headers(
    *,
    org_id: uuid.UUID = ORG_ID,
    external_id: str = TEST_USER_EXTERNAL,
) -> dict[str, str]:
    token = f"shiprate-test:{external_id}:{org_id}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def async_engine():
    engine = create_async_engine(database_url(), echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session, session.begin():
        yield session
        await session.rollback()


async def ensure_test_identity(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": str(ORG_ID)},
    )
    org = await session.get(Organization, ORG_ID)
    if org is None:
        session.add(
            Organization(
                id=ORG_ID,
                name="Test Org",
                slug="test-org",
                partner_id="jasci",
            )
        )
        await session.flush()
    user = await session.scalar(
        text("SELECT id FROM users WHERE external_auth_id = :eid"),
        {"eid": TEST_USER_EXTERNAL},
    )
    if user is None:
        uid = uuid.uuid4()
        session.add(User(id=uid, external_auth_id=TEST_USER_EXTERNAL, email="test@example.invalid"))
        session.add(
            OrganizationMembership(
                organization_id=ORG_ID,
                user_id=uid,
                role=MembershipRole.owner,
            )
        )
        await session.flush()
