"""TraceDesk orders, per-organization carrier contacts, cases, and claim packets.

Revision ID: 009_tracedesk
Revises: 008_auth_carrier
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009_tracedesk"
down_revision: str | None = "008_auth_carrier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = [
    "organization_carrier_contacts",
    "tracedesk_order_imports",
    "tracedesk_orders",
    "tracedesk_cases",
    "tracedesk_evidence",
    "tracedesk_claim_packets",
]


def _force_tenant(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
          USING (organization_id::text = app_current_organization_id())
          WITH CHECK (organization_id::text = app_current_organization_id());
        """
    )


def upgrade() -> None:
    op.create_table(
        "organization_carrier_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("carrier_code", sa.String(16), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("account_reference", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "carrier_code", name="uq_org_carrier_contact"),
    )
    op.create_index(
        "ix_organization_carrier_contacts_organization_id",
        "organization_carrier_contacts",
        ["organization_id"],
    )

    op.create_table(
        "tracedesk_order_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tracedesk_order_imports_organization_id", "tracedesk_order_imports", ["organization_id"])

    op.create_table(
        "tracedesk_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "import_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracedesk_order_imports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_order_id", sa.String(128), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(320), nullable=False),
        sa.Column("carrier_code", sa.String(16), nullable=False),
        sa.Column("tracking_reference", sa.String(128), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "external_order_id", name="uq_tracedesk_order_external"),
    )
    op.create_index("ix_tracedesk_orders_organization_id", "tracedesk_orders", ["organization_id"])

    op.create_table(
        "tracedesk_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracedesk_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("carrier_code", sa.String(16), nullable=False),
        sa.Column("tracking_reference", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("length_in", sa.Numeric(8, 2), nullable=False),
        sa.Column("width_in", sa.Numeric(8, 2), nullable=False),
        sa.Column("height_in", sa.Numeric(8, 2), nullable=False),
        sa.Column("contents_summary", sa.Text(), nullable=False),
        sa.Column("order_reference", sa.String(128), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_tracedesk_case_order"),
    )
    op.create_index("ix_tracedesk_cases_organization_id", "tracedesk_cases", ["organization_id"])

    op.create_table(
        "tracedesk_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracedesk_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("case_id", "kind", name="uq_tracedesk_evidence_kind"),
    )
    op.create_index("ix_tracedesk_evidence_organization_id", "tracedesk_evidence", ["organization_id"])
    op.create_index("ix_tracedesk_evidence_case_id", "tracedesk_evidence", ["case_id"])

    op.create_table(
        "tracedesk_claim_packets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tracedesk_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("details_json", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column("email_subject", sa.String(512), nullable=False),
        sa.Column("email_body", sa.Text(), nullable=False),
        sa.Column("recipient_label", sa.String(255), nullable=False),
        sa.Column("recipient_address", sa.String(512), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("case_id", name="uq_tracedesk_packet_case"),
    )
    op.create_index("ix_tracedesk_claim_packets_organization_id", "tracedesk_claim_packets", ["organization_id"])

    for table in TENANT_TABLES:
        _force_tenant(table)


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("tracedesk_claim_packets")
    op.drop_table("tracedesk_evidence")
    op.drop_table("tracedesk_cases")
    op.drop_table("tracedesk_orders")
    op.drop_table("tracedesk_order_imports")
    op.drop_table("organization_carrier_contacts")
