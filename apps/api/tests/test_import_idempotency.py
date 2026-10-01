"""import_jobs idempotency: same key must not duplicate jobs per organization."""

from __future__ import annotations

import uuid

import pytest
from conftest import first_import, skip_until_implemented

pytestmark = pytest.mark.integration


ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
IDEMPOTENCY_KEY = "sha256:abc123deadbeef"
SOURCE_SHA = "abc123deadbeef"


def _import_jobs():
    return skip_until_implemented(
        "import_jobs service",
        lambda: first_import(
            "app.services.import_jobs",
            "app.imports.jobs",
            "shiprate.services.import_jobs",
        ),
    )


@pytest.fixture
def import_jobs(require_db):
    return _import_jobs()


def test_same_idempotency_key_does_not_duplicate_import_job(import_jobs):
    create = getattr(import_jobs, "create_import_job", None)
    count = getattr(import_jobs, "count_import_jobs", None)

    if not all((create, count)):
        pytest.skip("create_import_job / count_import_jobs not implemented")

    payload = {
        "organization_id": ORG_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "source_file_sha256": SOURCE_SHA,
        "kind": "shipments_csv",
    }

    first = create(**payload)
    second = create(**payload)

    assert count(organization_id=ORG_ID, idempotency_key=IDEMPOTENCY_KEY) == 1

    def _row_id(row: object) -> object:
        if isinstance(row, dict):
            return row["id"]
        return row.id

    assert _row_id(second) == _row_id(first)
