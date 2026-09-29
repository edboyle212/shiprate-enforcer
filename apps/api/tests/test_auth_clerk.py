"""Clerk JWT verification."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from jose import JWTError

from app.auth.clerk import _jwks_url, verify_clerk_token
from app.config import settings


def test_jwks_url_from_issuer(monkeypatch):
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://clerk.example/")
    assert _jwks_url() == "https://clerk.example/.well-known/jwks.json"


def test_verify_clerk_token_requires_configuration():
    with patch.object(settings, "clerk_secret_key", ""), patch.object(settings, "clerk_jwt_issuer", ""):
        with pytest.raises(JWTError, match="clerk_not_configured"):
            verify_clerk_token("token")


def test_verify_clerk_token_decodes_with_jwks(monkeypatch):
    monkeypatch.setattr(settings, "clerk_jwt_issuer", "https://clerk.example")
    monkeypatch.setattr(settings, "clerk_secret_key", "sk_test")
    monkeypatch.setattr("app.auth.clerk._load_jwks", lambda: {"keys": []})
    monkeypatch.setattr("app.auth.clerk.jwt.decode", lambda *args, **kwargs: {"sub": "user_abc"})
    claims = verify_clerk_token("signed.jwt.token")
    assert claims["sub"] == "user_abc"
