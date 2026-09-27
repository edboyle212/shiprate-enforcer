"""Shared pytest helpers and import shims for the Building Agent layout."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_json_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / name
    if not path.is_file():
        pytest.fail(f"Missing fixture file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


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


@pytest.fixture(scope="session")
def golden_rating_request() -> dict[str, Any]:
    return load_json_fixture("golden_rating_request.json")


@pytest.fixture(scope="session")
def golden_rating_expected() -> dict[str, Any]:
    return load_json_fixture("golden_rating_expected.json")


def skip_until_implemented(feature: str, resolver: Callable[[], Any]):
    obj = resolver()
    if obj is None:
        pytest.skip(f"{feature} not implemented yet (Building Agent)")
    return obj


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def rls_available() -> bool:
    if os.environ.get("SHIPRATE_RLS_ENABLED", "").lower() in ("1", "true", "yes"):
        return True
    mod = first_import("app.db.rls", "app.database.rls", "shiprate.db.rls")
    if mod is None:
        return False
    return bool(getattr(mod, "RLS_ENABLED", False))


@pytest.fixture
def require_db(rls_available: bool):
    if not database_url():
        pytest.skip("DATABASE_URL / TEST_DATABASE_URL not set")
    yield
