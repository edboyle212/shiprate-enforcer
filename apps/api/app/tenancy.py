"""Request-scoped tenant context."""

from contextvars import ContextVar
from uuid import UUID

organization_id_ctx: ContextVar[UUID | None] = ContextVar("organization_id", default=None)


def get_organization_id() -> UUID | None:
    return organization_id_ctx.get()
