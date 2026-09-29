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
    set_organization_context(organization_id)
    _apply_org(session)
    if session.get(Organization, organization_id) is None:
        slug = f"org-{organization_id.hex}"
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


def _apply_org(session: Session) -> None:
    org_id = _org_ctx.get()
    session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": "" if org_id is None else str(org_id)},
    )


def create_test_shipment(
    *,
    organization_id: uuid.UUID,
    shipment_id: uuid.UUID,
    tracking_number: str,
) -> Shipment:
    with SessionLocal() as session:
        with session.begin():
            _apply_org(session)
            _ensure_organization(session, organization_id)
            existing = session.get(Shipment, shipment_id)
            if existing is not None:
                return existing
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
    with SessionLocal() as session:
        with session.begin():
            _apply_org(session)
            # No organization_id predicate: RLS must hide other tenants.
            rows = session.scalars(select(Shipment)).all()
            return list(rows)
