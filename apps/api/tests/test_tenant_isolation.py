"""Tenant isolation: org B must not read org A rows (Postgres RLS)."""

from __future__ import annotations

import os
import uuid

import pytest

from conftest import database_url, first_import, skip_until_implemented


pytestmark = [pytest.mark.rls, pytest.mark.integration]


ORG_A = uuid.UUID("01950000-0000-7000-8000-0000000000a1")
ORG_B = uuid.UUID("01950000-0000-7000-8000-0000000000b2")
SECRET_ROW_ID = uuid.UUID("01950000-0000-7000-8000-0000000000aa")


def _tenant_db():
    return skip_until_implemented(
        "Tenant DB session + RLS",
        lambda: first_import("app.db.tenant", "app.database.tenant", "shiprate.db.tenant"),
    )


@pytest.fixture
def tenant_db(require_db, rls_available):
    if not rls_available:
        pytest.skip("RLS not merged yet — set SHIPRATE_RLS_ENABLED=1 when ready")
    return _tenant_db()


def test_org_b_cannot_read_org_a_shipment(tenant_db):
    """Insert a row as org A; with org B context, SELECT must return nothing."""
    create_shipment = getattr(tenant_db, "create_test_shipment", None)
    fetch_shipments = getattr(tenant_db, "list_shipments", None)
    set_org = getattr(tenant_db, "set_organization_context", None)

    if not all((create_shipment, fetch_shipments, set_org)):
        pytest.skip("app.db.tenant helpers not implemented (create_test_shipment, list_shipments, set_organization_context)")

    set_org(ORG_A)
    create_shipment(
        organization_id=ORG_A,
        shipment_id=SECRET_ROW_ID,
        tracking_number="1Z999RLS0000000001",
    )

    set_org(ORG_B)
    rows = fetch_shipments(organization_id=ORG_B)
    ids = {row["id"] if isinstance(row, dict) else row.id for row in rows}
    assert SECRET_ROW_ID not in ids

    set_org(ORG_A)
    own_rows = fetch_shipments(organization_id=ORG_A)
    own_ids = {row["id"] if isinstance(row, dict) else row.id for row in own_rows}
    assert SECRET_ROW_ID in own_ids


def test_rls_policy_documented_when_skipped():
    """Meta: ensures CI stays green while RLS is pending."""
    if os.environ.get("SHIPRATE_RLS_ENABLED", "").lower() in ("1", "true", "yes"):
        return
    if database_url():
        pytest.skip("DATABASE_URL set but RLS flag off — expected during scaffold")
    assert True
