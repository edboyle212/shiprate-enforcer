"""Seed minimal org + user for Playwright / e2e (run after migrations)."""

from __future__ import annotations

import os
import uuid

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models import MembershipRole, Organization, OrganizationMembership, User

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
USER_EXTERNAL = "e2e-user"


def _sync_url() -> str:
    raw = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not raw:
        raise SystemExit("DATABASE_URL or TEST_DATABASE_URL required")
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


def main() -> None:
    engine = create_engine(_sync_url(), pool_pre_ping=True)
    with Session(engine) as session:
        with session.begin():
            session.execute(
                text("SELECT set_config('app.organization_id', :org_id, true)"),
                {"org_id": str(ORG_ID)},
            )
            if session.get(Organization, ORG_ID) is None:
                session.add(Organization(id=ORG_ID, name="E2E Org", slug="e2e-org", partner_id="northstar"))
            user = session.scalar(select(User).where(User.external_auth_id == USER_EXTERNAL))
            if user is None:
                user = User(id=uuid.uuid4(), external_auth_id=USER_EXTERNAL, email="e2e@example.invalid")
                session.add(user)
                session.flush()
            existing = session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == ORG_ID,
                    OrganizationMembership.user_id == user.id,
                )
            )
            if existing is None:
                session.add(
                    OrganizationMembership(
                        organization_id=ORG_ID,
                        user_id=user.id,
                        role=MembershipRole.owner,
                    )
                )
    print("seed_e2e: ok", ORG_ID)


if __name__ == "__main__":
    main()
