"""Compliance policies, matching, checks, and discrepancies.

Revision ID: 003_compliance
Revises: 002_wms_etl
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_compliance"
down_revision: Union[str, None] = "002_wms_etl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

match_type = postgresql.ENUM("exact", "normalized", "manual", name="match_type", create_type=False)
compliance_check_status = postgresql.ENUM(
    "passed", "failed", "error", name="compliance_check_status", create_type=False
)

TENANT_TABLES = [
    "compliance_policies",
    "shipment_invoice_matches",
    "compliance_checks",
    "discrepancies",
]


def upgrade() -> None:
    match_type.create(op.get_bind(), checkfirst=True)
    compliance_check_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "compliance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "rate_card_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rate_card_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("policy_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_compliance_policies_organization_id", "compliance_policies", ["organization_id"])

    op.create_table(
        "shipment_invoice_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shipment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "carrier_invoice_line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("carrier_invoice_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_type", match_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "carrier_invoice_line_id",
            name="uq_match_org_invoice_line",
        ),
    )
    op.create_index("ix_shipment_invoice_matches_organization_id", "shipment_invoice_matches", ["organization_id"])
    op.create_index("ix_shipment_invoice_matches_shipment_id", "shipment_invoice_matches", ["shipment_id"])

    op.create_table(
        "compliance_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shipment_invoice_match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shipment_invoice_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "compliance_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_policies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "rate_card_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rate_card_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("billed_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("allowed_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("variance_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column("within_tolerance", sa.Boolean(), nullable=False),
        sa.Column("status", compliance_check_status, nullable=False),
        sa.Column("rating_trace_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_compliance_checks_organization_id", "compliance_checks", ["organization_id"])
    op.create_index("ix_compliance_checks_match_id", "compliance_checks", ["shipment_invoice_match_id"])

    op.create_table(
        "discrepancies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "compliance_check_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_checks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("reason_codes", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("billed_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("allowed_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("variance_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column("trace_summary_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_discrepancies_organization_id", "discrepancies", ["organization_id"])

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
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


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("discrepancies")
    op.drop_table("compliance_checks")
    op.drop_table("shipment_invoice_matches")
    op.drop_table("compliance_policies")

    compliance_check_status.drop(op.get_bind(), checkfirst=True)
    match_type.drop(op.get_bind(), checkfirst=True)
