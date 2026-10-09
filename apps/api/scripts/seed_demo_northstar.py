"""Seed Northstar WMS demo partner, warehouse org, and approved rate card."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from demo.northstar_constants import (
    DEMO_ORG_ID,
    DEMO_ORG_NAME,
    DEMO_ORG_SLUG,
    DEMO_RATE_CARD_ID,
    DEMO_RATE_CARD_LABEL,
    DEMO_RATE_CARD_RULES,
    PARTNER_DISPLAY_NAME,
    PARTNER_ID,
)

from app.config import settings
from app.models import (
    MembershipRole,
    Organization,
    OrganizationMembership,
    PartnerMembership,
    RateCardVersion,
    RateCardVersionStatus,
    User,
    WmsPartner,
)

DEV_BOOTSTRAP_EXTERNAL = settings.dev_bootstrap_user_external_id


def _sync_url() -> str:
    raw = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not raw:
        raise SystemExit("DATABASE_URL or TEST_DATABASE_URL required")
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


def main() -> None:
    engine = create_engine(_sync_url(), pool_pre_ping=True)
    with Session(engine) as session, session.begin():
        session.execute(
            text("SELECT set_config('app.organization_id', :org_id, true)"),
            {"org_id": str(DEMO_ORG_ID)},
        )

        partner = session.get(WmsPartner, PARTNER_ID)
        if partner is None:
            session.add(
                WmsPartner(
                    partner_id=PARTNER_ID,
                    display_name=PARTNER_DISPLAY_NAME,
                    profile_json={
                        "partner_name": PARTNER_DISPLAY_NAME,
                        "ingest_mode": "file_drop",
                        "export_methods": ["ad_hoc_csv"],
                        "carriers": ["UPS"],
                    },
                    branding_json={
                        "display_name": PARTNER_DISPLAY_NAME,
                        "primary_color": "#0f766e",
                    },
                )
            )
        else:
            partner.display_name = PARTNER_DISPLAY_NAME

        org = session.get(Organization, DEMO_ORG_ID)
        if org is None:
            session.add(
                Organization(
                    id=DEMO_ORG_ID,
                    name=DEMO_ORG_NAME,
                    slug=DEMO_ORG_SLUG,
                    partner_id=PARTNER_ID,
                    settings_json={
                        "client_onboarding": {
                            "org_name": DEMO_ORG_NAME,
                            "carriers": ["UPS"],
                            "completed_at": datetime.now(UTC).isoformat(),
                        }
                    },
                )
            )
        else:
            org.partner_id = PARTNER_ID
            org.name = DEMO_ORG_NAME

        rc = session.get(RateCardVersion, DEMO_RATE_CARD_ID)
        if rc is None:
            session.add(
                RateCardVersion(
                    id=DEMO_RATE_CARD_ID,
                    organization_id=DEMO_ORG_ID,
                    carrier_code="UPS",
                    version_label=DEMO_RATE_CARD_LABEL,
                    rules_json=DEMO_RATE_CARD_RULES,
                    status=RateCardVersionStatus.approved,
                    approved_at=datetime.now(UTC),
                )
            )
        else:
            rc.rules_json = DEMO_RATE_CARD_RULES
            rc.status = RateCardVersionStatus.approved
            rc.approved_at = datetime.now(UTC)

        user = session.scalar(select(User).where(User.external_auth_id == DEV_BOOTSTRAP_EXTERNAL))
        if user is None:
            user = User(
                id=uuid.uuid4(),
                external_auth_id=DEV_BOOTSTRAP_EXTERNAL,
                email="dev-bootstrap@example.invalid",
            )
            session.add(user)
            session.flush()

        membership = session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == DEMO_ORG_ID,
                OrganizationMembership.user_id == user.id,
            )
        )
        if membership is None:
            session.add(
                OrganizationMembership(
                    organization_id=DEMO_ORG_ID,
                    user_id=user.id,
                    role=MembershipRole.owner,
                )
            )

        partner_membership = session.scalar(
            select(PartnerMembership).where(
                PartnerMembership.partner_id == PARTNER_ID,
                PartnerMembership.user_id == user.id,
            )
        )
        if partner_membership is None:
            session.add(
                PartnerMembership(
                    partner_id=PARTNER_ID,
                    user_id=user.id,
                    role="admin",
                )
            )

    print("seed_demo_northstar: ok")
    print(f"  partner_id={PARTNER_ID}")
    print(f"  organization_id={DEMO_ORG_ID}")


if __name__ == "__main__":
    main()
