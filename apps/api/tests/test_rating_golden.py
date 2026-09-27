"""Golden rating fixture: zone lookup + minimum charge (plan ticket 5)."""

from __future__ import annotations

import pytest

from conftest import first_import, skip_until_implemented


def _rating_engine():
    return skip_until_implemented(
        "rating engine",
        lambda: first_import(
            "app.rating.engine",
            "app.engine.rating",
            "shiprate.rating.engine",
        ),
    )


def test_golden_rating_allowed_total_and_trace(
    golden_rating_request,
    golden_rating_expected,
):
    engine = _rating_engine()
    rate = getattr(engine, "rate", None) or getattr(engine, "rate_shipment", None)
    if rate is None:
        pytest.skip("rate() / rate_shipment() not implemented on rating engine module")

    result = rate(golden_rating_request)
    if isinstance(result, dict):
        allowed = result["allowed_total_minor"]
        trace = result.get("trace") or result
    else:
        allowed = result.allowed_total_minor
        trace = result.trace if hasattr(result, "trace") else result.model_dump().get("trace", {})

    assert allowed == golden_rating_expected["allowed_total_minor"]

    for key in golden_rating_expected["trace_must_include"]:
        assert key in trace, f"trace missing required key {key!r}"

    for key, expected in golden_rating_expected["trace_assertions"].items():
        assert trace.get(key) == expected, f"trace[{key!r}] mismatch"
