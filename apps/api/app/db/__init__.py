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
    """Apply tenant context for PostgreSQL RLS (SET LOCAL, transaction-scoped)."""
    if organization_id is None:
        await session.execute(text("SET LOCAL app.organization_id = ''"))
    else:
        await session.execute(
            text("SET LOCAL app.organization_id = :org_id"),
            {"org_id": str(organization_id)},
        )
