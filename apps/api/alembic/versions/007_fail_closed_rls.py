"""Fail-closed RLS — remove NULL bypass; enable etl_processed_objects RLS.

Revision ID: 007_fail_closed_rls
Revises: 006_negotiation
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_fail_closed_rls"
down_revision: str | None = "006_negotiation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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


def _recreate_tenant_policy(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
          USING (organization_id::text = app_current_organization_id())
          WITH CHECK (organization_id::text = app_current_organization_id());
        """
    )
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS org_tenant_select ON organizations")
    op.execute(
        """
        CREATE POLICY org_tenant_select ON organizations
          FOR SELECT
          USING (id::text = app_current_organization_id());
        """
    )
    op.execute(
        """
        CREATE POLICY org_tenant_update ON organizations
          FOR UPDATE
          USING (id::text = app_current_organization_id())
          WITH CHECK (id::text = app_current_organization_id());
        """
    )
    op.execute(
        """
        CREATE POLICY org_tenant_insert ON organizations
          FOR INSERT
          WITH CHECK (id::text = app_current_organization_id());
        """
    )
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")

    for table in TENANT_TABLES:
        _recreate_tenant_policy(table)


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        if table == "etl_processed_objects":
            op.execute("ALTER TABLE etl_processed_objects DISABLE ROW LEVEL SECURITY")
        else:
            op.execute(
                f"""
                CREATE POLICY {table}_tenant_isolation ON {table}
                  USING (
                    organization_id::text = app_current_organization_id()
                    OR app_current_organization_id() IS NULL
                  )
                  WITH CHECK (
                    organization_id::text = app_current_organization_id()
                    OR app_current_organization_id() IS NULL
                  );
                """
            )

    op.execute("DROP POLICY IF EXISTS org_tenant_insert ON organizations")
    op.execute("DROP POLICY IF EXISTS org_tenant_update ON organizations")
    op.execute("ALTER TABLE organizations NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY org_tenant_select ON organizations
          FOR SELECT
          USING (id::text = app_current_organization_id() OR app_current_organization_id() IS NULL);
        """
    )
