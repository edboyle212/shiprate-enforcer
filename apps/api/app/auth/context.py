from contextvars import ContextVar

from app.auth.principal import Principal

principal_ctx: ContextVar[Principal | None] = ContextVar("principal", default=None)


def get_principal() -> Principal | None:
    return principal_ctx.get()
