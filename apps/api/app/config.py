import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_async_url() -> str:
    raw = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if raw:
        if raw.startswith("postgresql+asyncpg://"):
            return raw
        if raw.startswith("postgresql://"):
            return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return "postgresql+asyncpg://shiprate:shiprate@localhost:5432/shiprate"


def _default_sync_url() -> str:
    raw = os.environ.get("TEST_APP_DATABASE_URL")
    if raw:
        if raw.startswith("postgresql+asyncpg://"):
            return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql://", 1)
        return raw
    raw = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if raw:
        if raw.startswith("postgresql+asyncpg://"):
            return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql://", 1)
        return raw
    return "postgresql://shiprate:shiprate@localhost:5432/shiprate"


def migration_sync_url() -> str:
    """Sync URL for Alembic (superuser/migrator — not shiprate_app)."""
    raw = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if raw:
        if raw.startswith("postgresql+asyncpg://"):
            return raw.replace("postgresql+asyncpg://", "postgresql://", 1)
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql://", 1)
        return raw
    return "postgresql://shiprate:shiprate@localhost:5432/shiprate"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = _default_async_url()
    sync_database_url: str = _default_sync_url()

    # local | test | staging | production
    env: str = os.environ.get("ENV", "local").lower()

    # Clerk — production auth
    clerk_secret_key: str | None = None
    clerk_jwt_issuer: str | None = None
    dev_tenant_header: str = "X-Organization-Id"
    dev_bootstrap_user_external_id: str = "dev-bootstrap-user"

    outbound_carrier_send_enabled: bool = False

    # Object storage: MinIO when configured, else local filesystem
    s3_endpoint_url: str | None = None
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "shiprate-uploads"
    s3_region: str = "us-east-1"
    local_upload_dir: str = "./data/uploads"

    api_prefix: str = "/api/v1"

    etl_drop_root: str = "etl-drops"

    shiprate_ai_enabled: bool = False
    ai_jev_api_key: str | None = None
    ai_grok_api_key: str | None = None
    ai_claude_api_key: str | None = None

    # Dispute outbound mail (Resend) — platform sends so replies stay on your domain
    resend_api_key: str | None = None
    dispute_from_email: str | None = None
    dispute_reply_to: str | None = None


settings = Settings()


def allow_dev_tenant_header() -> bool:
    if settings.env == "production":
        return False
    raw = os.environ.get("ALLOW_DEV_TENANT_HEADER", "")
    return raw.lower() in ("1", "true", "yes")


def allow_test_bearer() -> bool:
    if settings.env == "production":
        return False
    if settings.env in ("test", "local"):
        raw = os.environ.get("SHIPRATE_ALLOW_TEST_BEARER", "1")
        return raw.lower() not in ("0", "false", "no")
    return False


def ai_enabled_globally() -> bool:
    raw = os.environ.get("SHIPRATE_AI_ENABLED", "")
    if raw.lower() in ("1", "true", "yes"):
        return True
    return bool(settings.shiprate_ai_enabled)
