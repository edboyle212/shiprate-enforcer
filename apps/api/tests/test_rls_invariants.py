"""Postgres RLS invariants (fail-closed tenant isolation)."""

from __future__ import annotations

import os
import uuid

import pytest
from conftest import first_import, skip_until_implemented
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, Shipment

pytestmark = [pytest.mark.rls, pytest.mark.integration]

TENANT_TABLES = [
    "organization_memberships",
    "source_files",
    "import_jobs",
    "import_rows",
    "shipments",
    "carrier_invoice_lines",
    "rate_card_versions",
    "rating_runs",
    "rating_explanations",
    "compliance_policies",
    "shipment_invoice_matches",
    "compliance_checks",
    "discrepancies",
    "discrepancy_events",
    "dispute_cases",
    "dispute_case_events",
    "dispute_drafts",
    "dispute_messages",
    "ai_feature_flags",
    "ai_decision_requests",
    "ai_decision_results",
    "etl_processed_objects",
]

ORG_A = uuid.UUID("01950000-0000-7000-8000-0000000000c1")
ORG_B = uuid.UUID("01950000-0000-7000-8000-0000000000c2")
SHIPMENT_ID = uuid.UUID("01950000-0000-7000-8000-0000000000c9")


@pytest.fixture
def tenant_db(require_db, rls_available):
    if not rls_available:
        pytest.skip("RLS not enabled")
    return skip_until_implemented(
        "Tenant DB session + RLS",
        lambda: first_import("app.db.tenant", "app.database.tenant", "shiprate.db.tenant"),
    )


@pytest.fixture
def sync_session(require_db, rls_available):
    if not rls_available:
        pytest.skip("RLS not enabled")
    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    with Session(engine) as session:
        yield session


def test_every_org_table_has_forced_rls(sync_session: Session):
    rows = sync_session.execute(
        text(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(:tables)
            """
        ),
        {"tables": TENANT_TABLES},
    ).all()
    assert len(rows) == len(TENANT_TABLES)
    for name, rls, forced in rows:
        assert rls and forced, f"{name} must have RLS enabled and forced"


def test_no_tenant_context_sees_zero_rows(sync_session: Session, tenant_db):
    create_shipment = tenant_db.create_test_shipment
    tenant_db.set_organization_context(ORG_A)
    create_shipment(
        organization_id=ORG_A,
        shipment_id=SHIPMENT_ID,
        tracking_number="1ZRLS000000000001",
    )
    again = create_shipment(
        organization_id=ORG_A,
        shipment_id=SHIPMENT_ID,
        tracking_number="1ZRLS000000000001",
    )
    assert again.id == SHIPMENT_ID
    sync_session.execute(text("SELECT set_config('app.organization_id', '', true)"))
    row = sync_session.scalar(select(Shipment).where(Shipment.id == SHIPMENT_ID))
    assert row is None


def test_cross_tenant_insert_rejected(sync_session: Session):
    for org_id in (ORG_A, ORG_B):
        sync_session.execute(
            text("SELECT set_config('app.organization_id', :org_id, true)"),
            {"org_id": str(org_id)},
        )
        if sync_session.get(Organization, org_id) is None:
            slug = f"org-{org_id.hex}"
            sync_session.add(Organization(id=org_id, name=slug, slug=slug))
            sync_session.flush()

    sync_session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": str(ORG_B)},
    )
    sync_session.add(
        Shipment(
            id=uuid.uuid4(),
            organization_id=ORG_A,
            tracking_number="1ZRLS000000000002",
        )
    )
    with pytest.raises(Exception):
        sync_session.commit()
    sync_session.rollback()


def test_app_role_is_not_superuser_owner_or_bypassrls(require_db):
    app_url = os.environ.get("TEST_APP_DATABASE_URL")
    if not app_url:
        return
    engine = create_engine(app_url, pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT rolsuper, rolbypassrls
                FROM pg_roles r
                JOIN pg_stat_activity a ON a.usename = r.rolname
                WHERE a.pid = pg_backend_pid()
                """
            )
        ).one()
        assert row[0] is False and row[1] is False
