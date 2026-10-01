"""Force RLS so the table owner cannot bypass tenant policies.

Revision ID: 005_force_rls
Revises: 004_disputes_ai
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005_force_rls"
down_revision: str | None = "004_disputes_ai"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that already have an organization_id isolation policy.
# organizations stays unforced: its policy is SELECT-only, and org bootstrap
# inserts must keep working for the table owner.
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
    "ai_feature_flags",
    "ai_decision_requests",
    "ai_decision_results",
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
