"""Replay: identical inputs + rule_bundle_hash must yield identical rating output."""

from __future__ import annotations

import hashlib
import json

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


def _canonical_result_payload(result) -> dict:
    if isinstance(result, dict):
        payload = {
            "allowed_total_minor": result["allowed_total_minor"],
            "currency_code": result.get("currency_code", "USD"),
            "status": result.get("status"),
            "trace": result.get("trace") or {},
        }
    else:
        payload = {
            "allowed_total_minor": result.allowed_total_minor,
            "currency_code": getattr(result, "currency_code", "USD"),
            "status": getattr(result, "status", None),
            "trace": getattr(result, "trace", {}),
        }
    return payload


def test_rating_replay_is_deterministic(golden_rating_request):
    engine = _rating_engine()
    rate = getattr(engine, "rate", None) or getattr(engine, "rate_shipment", None)
    replay = getattr(engine, "replay", None)

    if rate is None:
        pytest.skip("rate() not implemented")

    bundle_hash = golden_rating_request["rule_bundle_hash"]
    first = rate(golden_rating_request)
    second = rate({**golden_rating_request, "rule_bundle_hash": bundle_hash})

    first_payload = _canonical_result_payload(first)
    second_payload = _canonical_result_payload(second)

    assert first_payload == second_payload

    digest = hashlib.sha256(
        json.dumps(first_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    second_digest = hashlib.sha256(
        json.dumps(second_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert digest == second_digest

    if replay is not None:
        replayed = replay(
            inputs=golden_rating_request,
            rule_bundle_hash=bundle_hash,
            engine_version=golden_rating_request.get("engine_version", "0.1.0"),
        )
        assert _canonical_result_payload(replayed) == first_payload
