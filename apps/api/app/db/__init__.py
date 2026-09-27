from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def set_rls_organization(session: AsyncSession, organization_id: UUID | None) -> None:
    """Apply tenant context for PostgreSQL RLS.

    ``SET LOCAL`` cannot take a bound parameter. ``set_config(..., true)`` is the
    transaction-scoped equivalent and is safe to parameterize.
    """
    await session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": "" if organization_id is None else str(organization_id)},
    )
