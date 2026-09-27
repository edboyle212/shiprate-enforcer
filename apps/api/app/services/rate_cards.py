"""Rate card version service — draft vs approved immutability."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Organization, RateCardVersion, RateCardVersionStatus


def _ensure_organization(session, organization_id: uuid.UUID) -> None:
    if session.get(Organization, organization_id) is None:
        slug = f"org-{str(organization_id)[:8]}"
        session.add(Organization(id=organization_id, name=slug, slug=slug))
        session.flush()

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def _row_to_dict(row: RateCardVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "status": row.status.value,
        "rules_blob": row.rules_json,
    }


def get_rate_card_version(*, organization_id: uuid.UUID, rate_card_version_id: uuid.UUID) -> dict[str, Any]:
    with SessionLocal() as session:
        row = session.scalar(
            select(RateCardVersion).where(
                RateCardVersion.id == rate_card_version_id,
                RateCardVersion.organization_id == organization_id,
            )
        )
        if not row:
            raise ValueError("rate card version not found")
        return _row_to_dict(row)


def publish_rate_card_version(
    *,
    organization_id: uuid.UUID,
    rate_card_version_id: uuid.UUID,
    status: str,
    rules_blob: dict[str, Any],
) -> RateCardVersion:
    with SessionLocal() as session:
        with session.begin():
            _ensure_organization(session, organization_id)
            row = session.scalar(
                select(RateCardVersion).where(
                    RateCardVersion.id == rate_card_version_id,
                    RateCardVersion.organization_id == organization_id,
                )
            )
            if not row:
                row = RateCardVersion(
                    id=rate_card_version_id,
                    organization_id=organization_id,
                    carrier_code="UPS",
                    version_label="test",
                    rules_json=rules_blob,
                    status=RateCardVersionStatus.draft,
                )
                session.add(row)
            row.rules_json = rules_blob
            if status == "approved":
                row.status = RateCardVersionStatus.approved
                row.approved_at = datetime.now(UTC)
            session.flush()
            session.refresh(row)
            return row


def update_rate_card_version_rules(
    *,
    organization_id: uuid.UUID,
    rate_card_version_id: uuid.UUID,
    rules_blob: dict[str, Any],
) -> None:
    with SessionLocal() as session:
        with session.begin():
            row = session.scalar(
                select(RateCardVersion).where(
                    RateCardVersion.id == rate_card_version_id,
                    RateCardVersion.organization_id == organization_id,
                )
            )
            if not row:
                raise ValueError("rate card version not found")
            if row.status == RateCardVersionStatus.approved:
                raise PermissionError("approved rate card versions are immutable")
            row.rules_json = rules_blob
