"""Clerk JWT verification (JWKS)."""

from __future__ import annotations

import time
from typing import Any

import httpx
from jose import JWTError, jwt

from app.config import settings

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600


def _jwks_url() -> str | None:
    issuer = settings.clerk_jwt_issuer
    if not issuer:
        return None
    base = issuer.rstrip("/")
    return f"{base}/.well-known/jwks.json"


def _load_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    url = _jwks_url()
    if not url:
        raise JWTError("clerk_issuer_not_configured")
    now = time.time()
    if _jwks_cache is not None and now - _jwks_fetched_at < _JWKS_TTL_SECONDS:
        return _jwks_cache
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = now
        return _jwks_cache


def verify_clerk_token(token: str) -> dict[str, Any]:
    if not settings.clerk_secret_key and not settings.clerk_jwt_issuer:
        raise JWTError("clerk_not_configured")
    jwks = _load_jwks()
    options = {"verify_aud": False}
    issuer = settings.clerk_jwt_issuer
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        issuer=issuer,
        options=options,
    )
