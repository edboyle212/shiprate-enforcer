"""Golden-path unit tests for compliance tolerance + reason codes (no DB)."""

from __future__ import annotations

from app.rating.engine import rate as rate_shipment
from app.services.compliance import (
    DEFAULT_ABSOLUTE_TOLERANCE_MINOR,
    build_rating_request,
    derive_reason_codes,
    tolerance_threshold_minor,
    within_tolerance,
    ToleranceConfig,
)
from conftest import load_json_fixture


def test_default_tolerance_threshold_uses_absolute_floor():
    tolerances = ToleranceConfig()
    assert tolerance_threshold_minor(100, tolerances) == DEFAULT_ABSOLUTE_TOLERANCE_MINOR
    assert tolerance_threshold_minor(50_000, tolerances) == 1000  # 2% of 50_000


def test_within_tolerance_allows_underage_and_small_overage():
    tolerances = ToleranceConfig(absolute_minor=500, percent=2)
    assert within_tolerance(500, 500, tolerances)
    assert within_tolerance(400, 500, tolerances)
    assert within_tolerance(900, 500, tolerances)
    assert not within_tolerance(1100, 500, tolerances)


def test_golden_rating_produces_discrepancy_reason_codes_when_over_billed():
    request = load_json_fixture("golden_rating_request.json")
    result = rate_shipment(request)
    allowed = result["allowed_total_minor"]
    billed = allowed + 1000
    trace = result["trace"]
    codes = derive_reason_codes(trace=trace, variance_minor=billed - allowed)
    assert "BASE_RATE" in codes
    assert "MINIMUM_CHARGE" in codes
    assert "BILLED_OVER_ALLOWED" in codes


def test_build_rating_request_maps_shipment_fields():
    from types import SimpleNamespace

    shipment = SimpleNamespace(
        service_code="GND",
        dest_postal="10001",
        origin_postal="60601",
        currency_code="USD",
        weight_oz=4,
    )
    card = SimpleNamespace(id="01950000-0000-7000-8000-000000000030", rules_json={"zones": {"10001": 2}})
    payload = build_rating_request(shipment, card)  # type: ignore[arg-type]
    assert payload["service_level"] == "GND"
    assert payload["packages"][0]["actual_weight_oz"] == 4
