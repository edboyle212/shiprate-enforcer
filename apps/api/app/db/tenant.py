"""Sync DB helpers for RLS integration tests."""

from __future__ import annotations

import os
import uuid
from contextvars import ContextVar
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Organization, Shipment


def _ensure_organization(session: Session, organization_id: uuid.UUID) -> None:
    if session.get(Organization, organization_id) is None:
        slug = f"org-{str(organization_id)[:8]}"
        session.add(
            Organization(
                id=organization_id,
                name=slug,
                slug=slug,
            )
        )
        session.flush()

RLS_ENABLED = os.environ.get("SHIPRATE_RLS_ENABLED", "").lower() in ("1", "true", "yes")

_org_ctx: ContextVar[uuid.UUID | None] = ContextVar("sync_org_id", default=None)

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def set_organization_context(organization_id: uuid.UUID) -> None:
    _org_ctx.set(organization_id)


def _session_with_rls() -> Session:
    session = SessionLocal()
    org_id = _org_ctx.get()
    if org_id is not None:
        session.execute(
            text("SET LOCAL app.organization_id = :org_id"),
            {"org_id": str(org_id)},
        )
    return session


def create_test_shipment(
    *,
    organization_id: uuid.UUID,
    shipment_id: uuid.UUID,
    tracking_number: str,
) -> Shipment:
    with _session_with_rls() as session:
        with session.begin():
            _ensure_organization(session, organization_id)
            row = Shipment(
                id=shipment_id,
                organization_id=organization_id,
                tracking_number=tracking_number,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return row


def list_shipments(*, organization_id: uuid.UUID) -> list[Shipment | dict[str, Any]]:
    set_organization_context(organization_id)
    with _session_with_rls() as session:
        with session.begin():
            rows = session.scalars(
                select(Shipment).where(Shipment.organization_id == organization_id)
            ).all()
            return list(rows)
