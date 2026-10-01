"""Compliance: billed above allowed + tolerance yields discrepancy with reason code."""

from __future__ import annotations

import uuid

import pytest
from conftest import first_import, skip_until_implemented

ALLOWED_MINOR = 10_000
TOLERANCE_ABSOLUTE_MINOR = 500
BILLED_WITHIN = ALLOWED_MINOR + TOLERANCE_ABSOLUTE_MINOR
BILLED_OVER = ALLOWED_MINOR + TOLERANCE_ABSOLUTE_MINOR + 1

EXPECTED_REASON_CODES = frozenset(
    {
        "BILLED_EXCEEDS_ALLOWED",
        "billed_exceeds_allowed",
        "OVER_TOLERANCE",
        "over_tolerance",
    }
)


def _compliance():
    return skip_until_implemented(
        "compliance engine",
        lambda: first_import(
            "app.services.compliance",
            "app.compliance.engine",
            "shiprate.compliance",
        ),
    )


def _evaluate(compliance):
    return getattr(compliance, "evaluate_compliance", None) or getattr(
        compliance, "check_line_compliance", None
    )


def _reason_code(result) -> str:
    if result is None:
        return ""
    if isinstance(result, dict):
        return str(result.get("reason_code") or result.get("code") or "")
    return str(getattr(result, "reason_code", "") or getattr(result, "code", ""))


def test_no_discrepancy_when_billed_within_allowed_plus_tolerance():
    compliance = _compliance()
    evaluate = _evaluate(compliance)
    if not evaluate:
        pytest.skip("evaluate_compliance / check_line_compliance not implemented")

    result = evaluate(
        billed_amount_minor=BILLED_WITHIN,
        allowed_amount_minor=ALLOWED_MINOR,
        tolerance_absolute_minor=TOLERANCE_ABSOLUTE_MINOR,
    )
    assert result is None or _reason_code(result) == ""


def test_discrepancy_when_billed_exceeds_allowed_plus_tolerance():
    compliance = _compliance()
    evaluate = _evaluate(compliance)
    if not evaluate:
        pytest.skip("evaluate_compliance / check_line_compliance not implemented")

    result = evaluate(
        billed_amount_minor=BILLED_OVER,
        allowed_amount_minor=ALLOWED_MINOR,
        tolerance_absolute_minor=TOLERANCE_ABSOLUTE_MINOR,
    )
    assert result is not None
    reason = _reason_code(result)
    assert reason in EXPECTED_REASON_CODES, f"unexpected reason_code {reason!r}"


ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")
INVOICE_LINE_ID = uuid.UUID("01950000-0000-7000-8000-000000000202")
RATING_RUN_ID = uuid.UUID("01950000-0000-7000-8000-000000000050")


@pytest.fixture
def compliance(require_db):
    return _compliance()


@pytest.mark.integration
def test_compliance_run_persists_discrepancy_with_reason_code(compliance):
    run = getattr(compliance, "run_compliance_for_invoice_line", None) or getattr(
        compliance, "create_discrepancy_for_line", None
    )
    list_rows = getattr(compliance, "list_discrepancies", None) or getattr(
        compliance, "get_discrepancies_for_invoice_line", None
    )
    if not run or not list_rows:
        pytest.skip("run_compliance_for_invoice_line / list_discrepancies not implemented")

    run(
        organization_id=ORG_ID,
        carrier_invoice_line_id=INVOICE_LINE_ID,
        rating_run_id=RATING_RUN_ID,
        billed_amount_minor=BILLED_OVER,
        allowed_amount_minor=ALLOWED_MINOR,
        tolerance_absolute_minor=TOLERANCE_ABSOLUTE_MINOR,
    )

    rows = list_rows(organization_id=ORG_ID, carrier_invoice_line_id=INVOICE_LINE_ID)
    assert rows, "expected at least one persisted discrepancy"
    first = rows[0]
    reason = _reason_code(first)
    assert reason in EXPECTED_REASON_CODES, f"unexpected persisted reason_code {reason!r}"
