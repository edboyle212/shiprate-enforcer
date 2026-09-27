"""Approved rate_card_version rows must not be mutated in place."""

from __future__ import annotations

import uuid

import pytest

from conftest import first_import, skip_until_implemented

pytestmark = pytest.mark.integration

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
VERSION_ID = uuid.UUID("01950000-0000-7000-8000-000000000040")


def _rate_cards():
    return skip_until_implemented(
        "rate card versioning",
        lambda: first_import(
            "app.services.rate_cards",
            "app.contracts.rate_cards",
            "shiprate.services.rate_cards",
        ),
    )


@pytest.fixture
def rate_cards(require_db):
    return _rate_cards()


def test_approved_rate_card_version_cannot_be_updated_in_place(rate_cards):
    publish = getattr(rate_cards, "publish_rate_card_version", None)
    mutate = getattr(rate_cards, "update_rate_card_version_rules", None)
    get_version = getattr(rate_cards, "get_rate_card_version", None)

    if not all((publish, mutate, get_version)):
        pytest.skip("publish_rate_card_version / update_rate_card_version_rules / get_rate_card_version not implemented")

    publish(
        organization_id=ORG_ID,
        rate_card_version_id=VERSION_ID,
        status="approved",
        rules_blob={"minimum_charge_minor": {"GND": 500}},
    )

    before = get_version(organization_id=ORG_ID, rate_card_version_id=VERSION_ID)
    before_rules = before["rules_blob"] if isinstance(before, dict) else before.rules_blob

    with pytest.raises((PermissionError, ValueError)) as exc:
        mutate(
            organization_id=ORG_ID,
            rate_card_version_id=VERSION_ID,
            rules_blob={"minimum_charge_minor": {"GND": 999}},
        )

    assert "immutable" in str(exc.value).lower() or "approved" in str(exc.value).lower()

    after = get_version(organization_id=ORG_ID, rate_card_version_id=VERSION_ID)
    after_rules = after["rules_blob"] if isinstance(after, dict) else after.rules_blob
    assert after_rules == before_rules
