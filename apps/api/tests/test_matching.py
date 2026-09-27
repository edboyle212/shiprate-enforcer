"""Tracking-based match: normalize identifiers; no match when tracking missing."""

from __future__ import annotations

import uuid

import pytest

from conftest import first_import, skip_until_implemented


def _matching():
    return skip_until_implemented(
        "tracking matching",
        lambda: first_import(
            "app.services.matching",
            "app.matching.engine",
            "shiprate.matching",
        ),
    )


def _normalize(matching):
    return getattr(matching, "normalize_tracking_number", None) or getattr(
        matching, "normalize_tracking", None
    )


def _match_pair(matching):
    match_pair = getattr(matching, "match_invoice_line_to_shipment", None)
    if match_pair is not None:
        return match_pair
    match_pair = getattr(matching, "tracking_numbers_match", None)
    if match_pair is not None:
        return match_pair
    return getattr(matching, "match_by_tracking", None)


def test_normalized_tracking_numbers_match_equivalent_formats():
    matching = _matching()
    normalize = _normalize(matching)
    match_pair = _match_pair(matching)
    if not normalize or not match_pair:
        pytest.skip("normalize_tracking_number / match helpers not implemented")

    left = " 1z999RLS0000000001 "
    right = "1Z999RLS0000000001"

    assert normalize(left) == normalize(right)
    assert match_pair(shipment_tracking=left, invoice_tracking=right) is True


def test_no_match_when_shipment_tracking_missing():
    matching = _matching()
    match_pair = _match_pair(matching)
    if not match_pair:
        pytest.skip("match_invoice_line_to_shipment / tracking_numbers_match not implemented")

    assert match_pair(shipment_tracking=None, invoice_tracking="1Z999RLS0000000001") is False
    assert match_pair(shipment_tracking="", invoice_tracking="1Z999RLS0000000001") is False


def test_no_match_when_invoice_tracking_missing():
    matching = _matching()
    match_pair = _match_pair(matching)
    if not match_pair:
        pytest.skip("match_invoice_line_to_shipment / tracking_numbers_match not implemented")

    assert match_pair(shipment_tracking="1Z999RLS0000000001", invoice_tracking=None) is False
    assert match_pair(shipment_tracking="1Z999RLS0000000001", invoice_tracking="") is False


ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
SHIPMENT_ID = uuid.UUID("01950000-0000-7000-8000-000000000101")
INVOICE_LINE_ID = uuid.UUID("01950000-0000-7000-8000-000000000201")


@pytest.fixture
def matching(require_db):
    return _matching()


@pytest.mark.integration
def test_persisted_match_links_shipment_to_invoice_line(matching):
    persist = getattr(matching, "persist_tracking_match", None) or getattr(
        matching, "link_invoice_line_to_shipment", None
    )
    lookup = getattr(matching, "get_match_for_invoice_line", None) or getattr(
        matching, "find_shipment_for_invoice_line", None
    )
    if not persist or not lookup:
        pytest.skip("persist_tracking_match / get_match_for_invoice_line not implemented")

    persist(
        organization_id=ORG_ID,
        shipment_id=SHIPMENT_ID,
        carrier_invoice_line_id=INVOICE_LINE_ID,
        shipment_tracking="1Z999RLS0000000001",
        invoice_tracking=" 1z999RLS0000000001 ",
    )

    result = lookup(organization_id=ORG_ID, carrier_invoice_line_id=INVOICE_LINE_ID)
    shipment_id = getattr(result, "shipment_id", None) or (
        result.get("shipment_id") if isinstance(result, dict) else None
    )
    assert shipment_id == SHIPMENT_ID
