"""Shared pytest configuration and fixtures."""

from __future__ import annotations

pytest_plugins = ["tests.db"]

import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest
import uuid

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
ORG_HEADER = {"X-Organization-Id": str(ORG_ID)}


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("ENV", "test")
    os.environ.setdefault("ALLOW_DEV_TENANT_HEADER", "1")
    os.environ.setdefault("SHIPRATE_ALLOW_TEST_BEARER", "1")
    if os.environ.get("CI") == "true":
        os.environ.setdefault("SHIPRATE_REQUIRE_DATABASE", "1")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("SHIPRATE_FAIL_ON_SKIP") == "1":
        for item in items:
            if "skip" in item.keywords:
                item.add_marker(pytest.mark.xfail(reason="skips forbidden in CI", strict=True))


def try_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def first_import(*module_names: str):
    for name in module_names:
        mod = try_import(name)
        if mod is not None:
            return mod
    return None


def load_json_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / name
    if not path.is_file():
        pytest.fail(f"Missing fixture file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def golden_rating_request() -> dict[str, Any]:
    return load_json_fixture("golden_rating_request.json")


@pytest.fixture(scope="session")
def golden_rating_expected() -> dict[str, Any]:
    return load_json_fixture("golden_rating_expected.json")


@pytest.fixture(scope="session")
def rls_available() -> bool:
    return os.environ.get("SHIPRATE_RLS_ENABLED", "").lower() in ("1", "true", "yes")


@pytest.fixture(scope="session")
def require_db():
    if os.environ.get("SHIPRATE_REQUIRE_DATABASE", "").lower() in ("1", "true", "yes"):
        if not database_url():
            pytest.fail("TEST_DATABASE_URL is required when SHIPRATE_REQUIRE_DATABASE=1")
    elif not database_url():
        pytest.skip("DATABASE_URL / TEST_DATABASE_URL not set")
    yield


@pytest.fixture
def api_client(require_db):
    from unittest.mock import AsyncMock

    from app.db import get_db
    from app.main import app

    session = AsyncMock()

    async def _fake_db():
        yield session

    app.dependency_overrides[get_db] = _fake_db
    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.headers.update(ORG_HEADER)
    from tests.db import admin_auth_headers

    client.headers.update(admin_auth_headers())
    yield client, session
    app.dependency_overrides.clear()


def skip_until_implemented(feature: str, resolver: Callable[[], Any]):
    obj = resolver()
    if obj is None:
        pytest.fail(f"{feature} not implemented")
    return obj
