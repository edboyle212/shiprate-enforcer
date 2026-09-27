from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.tenancy import organization_id_ctx


class TenancyMiddleware(BaseHTTPMiddleware):
    """
    Dev: resolve tenant from X-Organization-Id.
    Production: Clerk JWT org claim (stub — set CLERK_* env when wiring auth).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        org_id: UUID | None = None
        header_value = request.headers.get(settings.dev_tenant_header)
        if header_value:
            try:
                org_id = UUID(header_value)
            except ValueError:
                pass

        if org_id is None and settings.clerk_secret_key:
            # Stub: extract org from Authorization when Clerk is configured
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer ") and request.headers.get("X-Clerk-Org-Id"):
                try:
                    org_id = UUID(request.headers["X-Clerk-Org-Id"])
                except ValueError:
                    pass

        token = organization_id_ctx.set(org_id)
        try:
            response = await call_next(request)
            if org_id:
                response.headers["X-Organization-Id"] = str(org_id)
            return response
        finally:
            organization_id_ctx.reset(token)
