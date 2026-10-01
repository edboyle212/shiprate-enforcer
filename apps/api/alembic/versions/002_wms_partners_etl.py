"""WMS partner profiles and ETL drop tracking.

Revision ID: 002_wms_etl
Revises: 001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_wms_etl"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wms_partners",
        sa.Column("partner_id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("profile_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("branding_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "etl_processed_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "storage_key", name="uq_etl_processed_key"),
    )
    op.create_index("ix_etl_processed_objects_organization_id", "etl_processed_objects", ["organization_id"])


def downgrade() -> None:
    op.drop_table("etl_processed_objects")
    op.drop_table("wms_partners")
