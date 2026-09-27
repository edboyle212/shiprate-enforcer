"""Dispute cases, discrepancy review, AI decision logging, feature flags.

Revision ID: 004_disputes_ai
Revises: 003_compliance
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_disputes_ai"
down_revision: Union[str, None] = "003_compliance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

discrepancy_review_status = postgresql.ENUM(
    "open", "approved", "rejected", "hold", name="discrepancy_review_status", create_type=False
)
dispute_case_status = postgresql.ENUM("open", "closed", name="dispute_case_status", create_type=False)
dispute_draft_status = postgresql.ENUM("draft", "approved", name="dispute_draft_status", create_type=False)

TENANT_TABLES = [
    "discrepancy_events",
    "dispute_cases",
    "dispute_case_events",
    "dispute_drafts",
    "ai_feature_flags",
    "ai_decision_requests",
    "ai_decision_results",
]


def upgrade() -> None:
    discrepancy_review_status.create(op.get_bind(), checkfirst=True)
    dispute_case_status.create(op.get_bind(), checkfirst=True)
    dispute_draft_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "discrepancies",
        sa.Column(
            "review_status",
            discrepancy_review_status,
            server_default="open",
            nullable=False,
        ),
    )
    op.add_column("discrepancies", sa.Column("review_comment", sa.Text(), nullable=True))
    op.add_column("discrepancies", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "discrepancy_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "discrepancy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discrepancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_discrepancy_events_organization_id", "discrepancy_events", ["organization_id"])
    op.create_index("ix_discrepancy_events_discrepancy_id", "discrepancy_events", ["discrepancy_id"])

    op.create_table(
        "dispute_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "discrepancy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discrepancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column(
            "status",
            dispute_case_status,
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "discrepancy_id", name="uq_dispute_case_org_discrepancy"),
    )
    op.create_index("ix_dispute_cases_organization_id", "dispute_cases", ["organization_id"])

    op.create_table(
        "dispute_case_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dispute_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dispute_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_dispute_case_events_organization_id", "dispute_case_events", ["organization_id"])
    op.create_index("ix_dispute_case_events_dispute_case_id", "dispute_case_events", ["dispute_case_id"])

    op.create_table(
        "dispute_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dispute_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dispute_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_subject", sa.String(512), nullable=False),
        sa.Column("email_body", sa.Text(), nullable=False),
        sa.Column(
            "status",
            dispute_draft_status,
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dispute_drafts_organization_id", "dispute_drafts", ["organization_id"])
    op.create_index("ix_dispute_drafts_dispute_case_id", "dispute_drafts", ["dispute_case_id"])

    op.create_table(
        "ai_feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature_key", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "feature_key", name="uq_ai_feature_org_key"),
    )
    op.create_index("ix_ai_feature_flags_organization_id", "ai_feature_flags", ["organization_id"])

    op.create_table(
        "ai_decision_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision_type", sa.String(64), nullable=False),
        sa.Column("input_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ai_decision_requests_organization_id", "ai_decision_requests", ["organization_id"])

    op.create_table(
        "ai_decision_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_decision_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("output_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("used_ai", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ai_decision_results_organization_id", "ai_decision_results", ["organization_id"])
    op.create_index("ix_ai_decision_results_request_id", "ai_decision_results", ["request_id"])

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

    op.drop_table("ai_decision_results")
    op.drop_table("ai_decision_requests")
    op.drop_table("ai_feature_flags")
    op.drop_table("dispute_drafts")
    op.drop_table("dispute_case_events")
    op.drop_table("dispute_cases")
    op.drop_table("discrepancy_events")

    op.drop_column("discrepancies", "reviewed_at")
    op.drop_column("discrepancies", "review_comment")
    op.drop_column("discrepancies", "review_status")

    dispute_draft_status.drop(op.get_bind(), checkfirst=True)
    dispute_case_status.drop(op.get_bind(), checkfirst=True)
    discrepancy_review_status.drop(op.get_bind(), checkfirst=True)
