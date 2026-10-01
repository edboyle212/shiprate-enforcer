from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import allow_dev_tenant_header, settings
from app.middleware.auth import AuthMiddleware
from app.routers import (
    ai,
    compliance,
    disputes,
    etl,
    health,
    imports,
    matching,
    orgs,
    partners,
    rating,
    reporting,
)

app = FastAPI(title="Shiprate Enforcer API", version="0.1.0")


@app.on_event("startup")
def _validate_security_config() -> None:
    if settings.env == "production" and allow_dev_tenant_header():
        raise RuntimeError("ALLOW_DEV_TENANT_HEADER must not be set in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:43123", "http://127.0.0.1:43123"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

prefix = settings.api_prefix
app.include_router(health.router, prefix=prefix, tags=["health"])
app.include_router(orgs.router, prefix=prefix, tags=["organizations"])
app.include_router(partners.router, prefix=prefix, tags=["partners"])
app.include_router(imports.router, prefix=prefix, tags=["imports"])
app.include_router(etl.router, prefix=prefix, tags=["etl"])
app.include_router(rating.router, prefix=prefix, tags=["rating"])
app.include_router(matching.router, prefix=prefix, tags=["matching"])
app.include_router(compliance.router, prefix=prefix, tags=["compliance"])
app.include_router(disputes.router, prefix=prefix, tags=["disputes"])
app.include_router(reporting.router, prefix=prefix, tags=["reporting"])
app.include_router(ai.router, prefix=prefix, tags=["ai"])
