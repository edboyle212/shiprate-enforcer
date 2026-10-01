"""Sync DB services with mocked SessionLocal (no Postgres required)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db import tenant as tenant_db
from app.models import (
    ImportJob,
    ImportJobStatus,
    RateCardVersion,
    RateCardVersionStatus,
)
from app.services import import_jobs as import_jobs_service
from app.services import rate_cards as rate_cards_service
from tests.conftest import ORG_ID


def _mock_session_local(session: MagicMock):
    outer = MagicMock()
    outer.__enter__.return_value = session
    outer.__exit__.return_value = None
    session.begin.return_value = outer
    return outer


def test_create_import_job_idempotent():
    session = MagicMock()
    existing = ImportJob(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        source_file_id=uuid.uuid4(),
        idempotency_key="k1",
        sha256_hex="abc",
        status=ImportJobStatus.pending,
    )
    session.scalar.return_value = existing
    local = _mock_session_local(session)

    with patch.object(import_jobs_service, "SessionLocal", return_value=local):
        job = import_jobs_service.create_import_job(
            organization_id=ORG_ID,
            idempotency_key="k1",
            source_file_sha256="abc",
            kind="shipment_export",
        )
    assert job.id == existing.id


def test_count_import_jobs():
    session = MagicMock()
    session.scalar.return_value = 2
    local = _mock_session_local(session)
    with patch.object(import_jobs_service, "SessionLocal", return_value=local):
        count = import_jobs_service.count_import_jobs(organization_id=ORG_ID, idempotency_key="k1")
    assert count == 2


def test_rate_card_publish_and_immutable():
    session = MagicMock()
    rc_id = uuid.uuid4()
    row = RateCardVersion(
        id=rc_id,
        organization_id=ORG_ID,
        carrier_code="UPS",
        version_label="v1",
        rules_json={"a": 1},
        status=RateCardVersionStatus.approved,
    )
    session.scalar.return_value = row
    local = _mock_session_local(session)

    with patch.object(rate_cards_service, "SessionLocal", return_value=local):
        with pytest.raises(PermissionError):
            rate_cards_service.update_rate_card_version_rules(
                organization_id=ORG_ID,
                rate_card_version_id=rc_id,
                rules_blob={"b": 2},
            )

    session.scalar.return_value = None
    with patch.object(rate_cards_service, "SessionLocal", return_value=local):
        published = rate_cards_service.publish_rate_card_version(
            organization_id=ORG_ID,
            rate_card_version_id=rc_id,
            status="approved",
            rules_blob={"x": 1},
        )
    assert published.status == RateCardVersionStatus.approved

    session.scalar.return_value = row
    with patch.object(rate_cards_service, "SessionLocal", return_value=local):
        data = rate_cards_service.get_rate_card_version(organization_id=ORG_ID, rate_card_version_id=rc_id)
    assert data["status"] == "approved"


def test_tenant_helpers():
    session = MagicMock()
    local = _mock_session_local(session)
    session.get.return_value = None
    ship_id = uuid.uuid4()

    with patch.object(tenant_db, "SessionLocal", return_value=local):
        row = tenant_db.create_test_shipment(
            organization_id=ORG_ID,
            shipment_id=ship_id,
            tracking_number="1Z",
        )
    assert row.tracking_number == "1Z"
    session.add.assert_called()

    session.scalars.return_value.all.return_value = [row]
    with patch.object(tenant_db, "SessionLocal", return_value=local):
        listed = tenant_db.list_shipments(organization_id=ORG_ID)
    assert len(listed) == 1
