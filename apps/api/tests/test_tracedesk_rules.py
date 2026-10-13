"""Deterministic TraceDesk carrier rules."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.tracedesk_rules import (
    FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP,
    RULES,
    UPS_FILING_WINDOW_DAYS_FROM_SHIP,
    USPS_FILING_WINDOW_DAYS_FROM_SHIP,
    FilingWindow,
    TraceDetails,
    add_months,
    canonical_carrier,
    canonical_reason,
    filing_deadline,
    normalize_reference,
    rules_document,
    validate_details,
    validate_evidence,
)

UPS = "1Z999AA10123456784"
FEDEX = "123456789012"
USPS = "9400111899223344556677"
AS_OF = date(2026, 10, 13)
SHIP = date(2026, 10, 1)


def _details(**overrides) -> TraceDetails:
    payload = {
        "carrier": "UPS",
        "tracking_reference": UPS,
        "reason": "loss",
        "length_in": 10,
        "width_in": 8,
        "height_in": 4,
        "contents_summary": "Two linen shirts",
        "order_reference": "100245",
        "ship_date": SHIP,
    }
    payload.update(overrides)
    return TraceDetails(**payload)


def test_uncertain_windows_use_named_constants():
    ups = RULES["UPS"]["loss"].window
    assert ups.uncertain is True
    assert ups.days == UPS_FILING_WINDOW_DAYS_FROM_SHIP
    assert ups.constant_name == "UPS_FILING_WINDOW_DAYS_FROM_SHIP"
    assert "UPS_FILING_WINDOW_DAYS_FROM_SHIP" in ups.source_note
    assert RULES["UPS"]["damage"].window == ups

    damage = RULES["FEDEX"]["damage"].window
    assert damage.uncertain is True
    assert damage.days == FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP
    assert "FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP" in damage.source_note

    loss = RULES["FEDEX"]["loss"].window
    assert loss.uncertain is False
    assert loss.months == 9
    assert loss.constant_name is None
    assert "tendered to FedEx" in loss.source_note

    usps = RULES["USPS"]["loss"].window
    assert usps.uncertain is False
    assert usps.days == USPS_FILING_WINDOW_DAYS_FROM_SHIP
    assert "mailing date" in usps.source_note
    assert RULES["USPS"]["damage"].window.source_note == usps.source_note


def test_fedex_loss_window_is_nine_calendar_months_from_ship_date():
    window = RULES["FEDEX"]["loss"].window
    assert add_months(date(2026, 1, 31), 9) == date(2026, 10, 31)
    assert add_months(date(2026, 5, 31), 9) == date(2027, 2, 28)
    deadline = filing_deadline(date(2026, 1, 31), window)
    accepted, errors = validate_details(
        _details(carrier="FedEx", tracking_reference=FEDEX, ship_date=date(2026, 1, 31)),
        as_of=deadline,
    )
    assert errors == []
    assert accepted is not None
    closed, closed_errors = validate_details(
        _details(carrier="FedEx", tracking_reference=FEDEX, ship_date=date(2026, 1, 31)),
        as_of=date(2026, 11, 1),
    )
    assert closed is None
    assert closed_errors[0].code == "window_closed"


def test_fedex_damage_window_uses_the_named_ship_date_constant():
    ship = date(2026, 3, 1)
    last_day = date(2026, 3, 22)
    accepted, errors = validate_details(
        _details(carrier="FEDEX", tracking_reference=FEDEX, reason="damage", ship_date=ship),
        as_of=last_day,
    )
    assert errors == []
    assert accepted is not None
    assert accepted.deadline == last_day
    closed, closed_errors = validate_details(
        _details(carrier="FEDEX", tracking_reference=FEDEX, reason="damage", ship_date=ship),
        as_of=date(2026, 3, 23),
    )
    assert closed is None
    assert closed_errors[0].code == "window_closed"


def test_ups_and_usps_windows_close_the_day_after_the_deadline():
    last_day = date(2026, 11, 30)
    for carrier, tracking in (("ups", UPS), ("USPS", USPS)):
        accepted, errors = validate_details(
            _details(carrier=carrier, tracking_reference=tracking, ship_date=SHIP),
            as_of=last_day,
        )
        assert errors == []
        assert accepted is not None
        closed, closed_errors = validate_details(
            _details(carrier=carrier, tracking_reference=tracking, ship_date=SHIP),
            as_of=date(2026, 12, 1),
        )
        assert closed is None
        assert closed_errors[0].code == "window_closed"


def test_reference_must_match_the_carrier_including_a_tracking_url():
    accepted, errors = validate_details(
        _details(tracking_reference="https://www.ups.com/track?tracknum=1Z999AA10123456784"),
        as_of=AS_OF,
    )
    assert errors == []
    assert accepted is not None
    assert accepted.tracking_reference == UPS

    fedex, fedex_errors = validate_details(
        _details(carrier="FedEx", tracking_reference="https://www.fedex.com/fedextrack/?trknbr=123456789012"),
        as_of=AS_OF,
    )
    assert fedex_errors == []
    assert fedex is not None
    assert fedex.tracking_reference == FEDEX

    usps, usps_errors = validate_details(
        _details(
            carrier="USPS",
            tracking_reference="https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111899223344556677",
        ),
        as_of=AS_OF,
    )
    assert usps_errors == []
    assert usps is not None

    rejected, reject_errors = validate_details(_details(tracking_reference=FEDEX), as_of=AS_OF)
    assert rejected is None
    assert reject_errors[0].code == "invalid_reference"
    assert normalize_reference("FEDEX", "1234567890123") is None
    assert normalize_reference("USPS", "9400") is None
    assert normalize_reference("UPS", "1Z123") is None


def test_required_fields_and_evidence_follow_carrier_and_reason():
    missing, errors = validate_details(_details(contents_summary="  ", length_in=0, reason="delay"), as_of=AS_OF)
    assert missing is None
    assert {error.code for error in errors} >= {"invalid_reason"}

    future, future_errors = validate_details(_details(ship_date=date(2026, 10, 20)), as_of=AS_OF)
    assert future is None
    assert future_errors[0].code == "ship_date_in_future"

    unknown, unknown_errors = validate_details(_details(carrier="DHL"), as_of=AS_OF)
    assert unknown is None
    assert unknown_errors[0].code == "unknown_carrier"

    assert validate_evidence("UPS", "loss", {"sales_invoice"}) == []
    assert validate_evidence("FEDEX", "loss", {"sales_invoice", "purchase_invoice"}) == []
    damage_errors = validate_evidence("USPS", "damage", {"sales_invoice"})
    assert damage_errors[0].code == "missing_evidence"
    assert "shipment photo" in damage_errors[0].message
    loss_errors = validate_evidence("UPS", "loss", {"shipment_photo"})
    assert loss_errors[0].code == "missing_evidence"
    assert "sales invoice" in loss_errors[0].message


def test_rules_document_exposes_windows_and_does_not_send():
    document = rules_document()
    assert document["email_sent_on_confirm"] is False
    assert document["carriers"] == ["UPS", "FEDEX", "USPS"]
    ups_loss = document["by_carrier"]["UPS"]["loss"]
    assert ups_loss["required_evidence"] == ["sales_invoice"]
    assert "purchase_invoice" in ups_loss["optional_evidence"]
    assert document["by_carrier"]["FEDEX"]["damage"]["filing_window"]["uncertain"] is True
    assert document["by_carrier"]["USPS"]["loss"]["filing_window"]["uncertain"] is False


def test_details_reject_blank_text_overlong_fields_and_a_missing_ship_date():
    assert canonical_carrier(None) is None
    assert canonical_reason(None) is None
    assert normalize_reference("UPS", None) is None
    assert normalize_reference("UPS", "   ") is None
    www = normalize_reference("UPS", "www.ups.com/track?tracknum=1Z999AA10123456784")
    assert www == UPS

    blank, errors = validate_details(
        _details(contents_summary="   ", order_reference="  ", length_in="nope", width_in=201, height_in=float("nan")),
        as_of=AS_OF,
    )
    assert blank is None
    assert {error.code for error in errors} >= {"invalid_dimension", "missing_field"}

    long_text, long_errors = validate_details(
        _details(contents_summary="x" * 2001, order_reference="y" * 129),
        as_of=AS_OF,
    )
    assert long_text is None
    assert any("2000" in error.message for error in long_errors)
    assert any("128" in error.message for error in long_errors)

    missing_ship, ship_errors = validate_details(_details(ship_date=None), as_of=AS_OF)
    assert missing_ship is None
    assert ship_errors[0].code == "missing_field"

    unknown_evidence = validate_evidence("DHL", "loss", {"sales_invoice", "postcard"})
    assert unknown_evidence[0].code == "unknown_carrier"
    extra = validate_evidence("UPS", "loss", {"sales_invoice", "postcard"})
    assert any(error.code == "invalid_evidence" for error in extra)

    empty_window = FilingWindow(days=None, months=None, uncertain=True, constant_name="EMPTY", source_note="none")
    with pytest.raises(ValueError, match="no duration"):
        filing_deadline(SHIP, empty_window)
