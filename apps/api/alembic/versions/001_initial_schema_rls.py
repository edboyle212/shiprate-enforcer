"""Initial schema with PostgreSQL RLS tenant policies.

Revision ID: 001_initial
Revises:
Create Date: 2026-09-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

membership_role = postgresql.ENUM("owner", "admin", "member", "viewer", name="membership_role", create_type=False)
source_file_kind = postgresql.ENUM(
    "shipment_export", "carrier_invoice", "rate_card", "other", name="source_file_kind", create_type=False
)
import_job_status = postgresql.ENUM(
    "pending", "processing", "completed", "failed", name="import_job_status", create_type=False
)
rate_card_version_status = postgresql.ENUM("draft", "approved", name="rate_card_version_status", create_type=False)
rating_run_status = postgresql.ENUM("pending", "completed", "failed", name="rating_run_status", create_type=False)

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
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    membership_role.create(op.get_bind(), checkfirst=True)
    source_file_kind.create(op.get_bind(), checkfirst=True)
    import_job_status.create(op.get_bind(), checkfirst=True)
    rate_card_version_status.create(op.get_bind(), checkfirst=True)
    rating_run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("partner_id", sa.String(64), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_auth_id", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", membership_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )
    op.create_index("ix_organization_memberships_organization_id", "organization_memberships", ["organization_id"])

    op.create_table(
        "source_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", source_file_kind, nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("storage_backend", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "sha256_hex", name="uq_source_file_org_sha"),
    )
    op.create_index("ix_source_files_organization_id", "source_files", ["organization_id"])

    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", import_job_status, nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_import_job_idempotency"),
    )
    op.create_index("ix_import_jobs_organization_id", "import_jobs", ["organization_id"])

    op.create_table(
        "import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_import_rows_organization_id", "import_rows", ["organization_id"])
    op.create_index("ix_import_rows_import_job_id", "import_rows", ["import_job_id"])

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tracking_number", sa.String(128), nullable=True),
        sa.Column("carrier_code", sa.String(32), nullable=True),
        sa.Column("service_code", sa.String(64), nullable=True),
        sa.Column("ship_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("origin_postal", sa.String(32), nullable=True),
        sa.Column("dest_postal", sa.String(32), nullable=True),
        sa.Column("weight_oz", sa.BigInteger(), nullable=True),
        sa.Column("package_count", sa.Integer(), nullable=True),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_shipments_organization_id", "shipments", ["organization_id"])
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"])

    op.create_table(
        "carrier_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tracking_number", sa.String(128), nullable=True),
        sa.Column("charge_code", sa.String(64), nullable=True),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("billed_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_carrier_invoice_lines_organization_id", "carrier_invoice_lines", ["organization_id"])
    op.create_index("ix_carrier_invoice_lines_tracking_number", "carrier_invoice_lines", ["tracking_number"])

    op.create_table(
        "rate_card_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("carrier_code", sa.String(32), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("status", rate_card_version_status, nullable=False),
        sa.Column("rules_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rate_card_versions_organization_id", "rate_card_versions", ["organization_id"])

    op.create_table(
        "rating_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rate_card_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rate_card_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", rating_run_status, nullable=False),
        sa.Column("input_snapshot_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("result_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rating_runs_organization_id", "rating_runs", ["organization_id"])

    op.create_table(
        "rating_explanations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rating_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("allowed_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default="USD", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rating_explanations_organization_id", "rating_explanations", ["organization_id"])
    op.create_index("ix_rating_explanations_rating_run_id", "rating_explanations", ["rating_run_id"])

    # RLS: session variable app.organization_id (SET LOCAL per transaction)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_organization_id() RETURNS text AS $$
          SELECT NULLIF(current_setting('app.organization_id', true), '');
        $$ LANGUAGE sql STABLE;
        """
    )

    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY org_tenant_select ON organizations
          FOR SELECT
          USING (id::text = app_current_organization_id() OR app_current_organization_id() IS NULL);
        """
    )

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

    op.execute("DROP POLICY IF EXISTS org_tenant_select ON organizations")
    op.execute("ALTER TABLE organizations DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS app_current_organization_id()")

    op.drop_table("rating_explanations")
    op.drop_table("rating_runs")
    op.drop_table("rate_card_versions")
    op.drop_table("carrier_invoice_lines")
    op.drop_table("shipments")
    op.drop_table("import_rows")
    op.drop_table("import_jobs")
    op.drop_table("source_files")
    op.drop_table("organization_memberships")
    op.drop_table("users")
    op.drop_table("organizations")

    rating_run_status.drop(op.get_bind(), checkfirst=True)
    rate_card_version_status.drop(op.get_bind(), checkfirst=True)
    import_job_status.drop(op.get_bind(), checkfirst=True)
    source_file_kind.drop(op.get_bind(), checkfirst=True)
    membership_role.drop(op.get_bind(), checkfirst=True)
