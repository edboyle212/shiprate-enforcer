"""Dispute negotiation messages, case fee snapshot, wider case status.

Revision ID: 006_negotiation
Revises: 005_force_rls
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_negotiation"
down_revision: str | None = "005_force_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

dispute_case_status_v2 = postgresql.ENUM(
    "open",
    "awaiting_approval",
    "awaiting_carrier",
    "awaiting_platform",
    "credited",
    "closed",
    name="dispute_case_status_v2",
)
dispute_message_direction = postgresql.ENUM(
    "outbound", "inbound", name="dispute_message_direction", create_type=False
)
dispute_message_status = postgresql.ENUM(
    "draft", "approved", "sent", name="dispute_message_status", create_type=False
)


def upgrade() -> None:
    dispute_case_status_v2.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE dispute_cases ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE dispute_cases
        ALTER COLUMN status TYPE dispute_case_status_v2
        USING status::text::dispute_case_status_v2
        """
    )
    op.execute("ALTER TABLE dispute_cases ALTER COLUMN status SET DEFAULT 'open'")
    op.execute("DROP TYPE dispute_case_status")
    op.execute("ALTER TYPE dispute_case_status_v2 RENAME TO dispute_case_status")

    op.add_column(
        "dispute_cases",
        sa.Column("autonomy_tier", sa.String(32), server_default="draft", nullable=False),
    )
    op.add_column(
        "dispute_cases",
        sa.Column("fee_bps", sa.Integer(), server_default="2000", nullable=False),
    )
    op.add_column("dispute_cases", sa.Column("recovered_amount_minor", sa.BigInteger(), nullable=True))
    op.add_column("dispute_cases", sa.Column("fee_amount_minor", sa.BigInteger(), nullable=True))

    dispute_message_direction.create(op.get_bind(), checkfirst=True)
    dispute_message_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "dispute_messages",
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
        sa.Column("direction", dispute_message_direction, nullable=False),
        sa.Column("email_subject", sa.String(512), nullable=False),
        sa.Column("email_body", sa.Text(), nullable=False),
        sa.Column("status", dispute_message_status, server_default="draft", nullable=False),
        sa.Column("round_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("offered_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("denied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dispute_messages_organization_id", "dispute_messages", ["organization_id"])
    op.create_index("ix_dispute_messages_dispute_case_id", "dispute_messages", ["dispute_case_id"])

    op.execute("ALTER TABLE dispute_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dispute_messages FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY dispute_messages_tenant_isolation ON dispute_messages
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
    op.execute("DROP POLICY IF EXISTS dispute_messages_tenant_isolation ON dispute_messages")
    op.execute("ALTER TABLE dispute_messages NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dispute_messages DISABLE ROW LEVEL SECURITY")
    op.drop_table("dispute_messages")
    dispute_message_status.drop(op.get_bind(), checkfirst=True)
    dispute_message_direction.drop(op.get_bind(), checkfirst=True)

    op.drop_column("dispute_cases", "fee_amount_minor")
    op.drop_column("dispute_cases", "recovered_amount_minor")
    op.drop_column("dispute_cases", "fee_bps")
    op.drop_column("dispute_cases", "autonomy_tier")

    old_status = postgresql.ENUM("open", "closed", name="dispute_case_status_old")
    old_status.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE dispute_cases ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE dispute_cases
        ALTER COLUMN status TYPE dispute_case_status_old
        USING CASE
          WHEN status::text IN ('open', 'closed') THEN status::text::dispute_case_status_old
          ELSE 'closed'::dispute_case_status_old
        END
        """
    )
    op.execute("DROP TYPE dispute_case_status")
    op.execute("ALTER TYPE dispute_case_status_old RENAME TO dispute_case_status")
    op.execute("ALTER TABLE dispute_cases ALTER COLUMN status SET DEFAULT 'open'")
