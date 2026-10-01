"""Unit tests for dispute draft content."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.disputes import build_dispute_draft_text


def test_dispute_draft_contains_trace_facts():
    disc = SimpleNamespace(
        billed_amount_minor=1500,
        allowed_amount_minor=1000,
        variance_minor=500,
        currency_code="USD",
    )
    trace = {
        "engine_version": "0.1.0",
        "zone": "3",
        "billable_weight_oz": 16,
        "minimum_charge_applied": False,
        "table_key": "ups_gnd_z3",
        "allowed_total_minor": 1000,
    }
    subject, body = build_dispute_draft_text(
        discrepancy=disc,
        claim_amount_minor=500,
        trace_summary=trace,
        reason_codes=["BILLED_OVER_ALLOWED", "OVER_TOLERANCE"],
    )
    assert "DRAFT" in body
    assert "not sent" in body.lower()
    assert "Zone: 3" in body
    assert "Billable weight (oz): 16" in body
    assert "ups_gnd_z3" in body
    assert "500" in subject or "5.00" in subject
