"""Platform admins, partner memberships, carrier contacts, discrepancy carrier_code.

Revision ID: 008_auth_carrier
Revises: 007_fail_closed_rls
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_auth_carrier"
down_revision: Union[str, None] = "007_fail_closed_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "partner_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("partner_id", sa.String(64), sa.ForeignKey("wms_partners.partner_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), server_default="admin", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("partner_id", "user_id", name="uq_partner_user"),
    )
    op.create_index("ix_partner_memberships_partner_id", "partner_memberships", ["partner_id"])
    op.create_index("ix_partner_memberships_user_id", "partner_memberships", ["user_id"])

    op.create_table(
        "carrier_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("carrier_code", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("address", sa.String(512), nullable=False),
        sa.Column(
            "verified_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("carrier_code", "channel", name="uq_carrier_contact_channel"),
    )

    op.add_column("discrepancies", sa.Column("carrier_code", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("discrepancies", "carrier_code")
    op.drop_table("carrier_contacts")
    op.drop_table("partner_memberships")
    op.drop_table("platform_admins")
