from __future__ import annotations

from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.auth.context import principal_ctx
from app.auth.principal import Principal
from app.auth.resolve import principal_from_bearer, principal_from_dev_header
from app.config import settings
from app.db import SessionLocal
from app.tenancy import organization_id_ctx


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate every request; set tenant context from verified principal only."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        principal: Principal | None = None
        org_id: UUID | None = None

        async with SessionLocal() as session:
            principal = await principal_from_bearer(session, request.headers.get("Authorization"))
            if principal is None:
                principal = await principal_from_dev_header(
                    session,
                    request.headers.get(settings.dev_tenant_header),
                    request.headers.get("X-Clerk-Org-Id"),
                )
            if principal is not None:
                org_id = principal.organization_id

        principal_token = principal_ctx.set(principal)
        org_token = organization_id_ctx.set(org_id)
        try:
            response = await call_next(request)
            if org_id:
                response.headers["X-Organization-Id"] = str(org_id)
            return response
        finally:
            organization_id_ctx.reset(org_token)
            principal_ctx.reset(principal_token)
