"""Per-carrier trace rules. Deterministic. No network and no mail."""

from __future__ import annotations

import math
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

CARRIERS = ("UPS", "FEDEX", "USPS")
REASONS = ("loss", "damage")
EVIDENCE_KINDS = ("shipment_photo", "sales_invoice", "purchase_invoice")

# UPS publishes claim timing from delivery or scheduled delivery, not ship date.
# TraceDesk measures every window from ship date, so this figure is a stand-in.
UPS_FILING_WINDOW_DAYS_FROM_SHIP = 60

# FedEx damage notice is 21 calendar days from delivery, not from ship date.
FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP = 21

# FedEx nondelivery claims are filed within 9 months after the package was tendered.
FEDEX_LOSS_FILING_WINDOW_MONTHS_FROM_SHIP = 9

# USPS DMM 609: file no later than 60 days from the mailing date.
USPS_FILING_WINDOW_DAYS_FROM_SHIP = 60

_UPS_REFERENCE = re.compile(r"1Z[0-9A-Z]{16}")
_FEDEX_REFERENCE = re.compile(r"(?:\d{12}|\d{15}|\d{20}|\d{22})")
_USPS_REFERENCE = re.compile(r"(?:\d{20}|\d{22}|\d{26}|\d{30}|\d{34}|[A-Z]{2}\d{9}[A-Z]{2})")
_REFERENCE = {"UPS": _UPS_REFERENCE, "FEDEX": _FEDEX_REFERENCE, "USPS": _USPS_REFERENCE}

_REFERENCE_HINT = {
    "UPS": "UPS references look like 1Z followed by 16 letters or digits.",
    "FEDEX": "FedEx references are 12, 15, 20, or 22 digits.",
    "USPS": "USPS references are 20, 22, 26, 30, or 34 digits, or a 13-character international number.",
}

_CARRIER_ALIASES = {
    "ups": "UPS",
    "fedex": "FEDEX",
    "fed ex": "FEDEX",
    "usps": "USPS",
}

_QUERY_KEYS = ("tracknum", "tracknums", "tracking", "trackingnumber", "trknbr", "tlabels", "q")

_DETAIL_FIELDS = (
    "tracking_reference",
    "reason",
    "dimensions",
    "contents_summary",
    "order_reference",
    "ship_date",
)

_UPS_SOURCE = (
    "Named constant UPS_FILING_WINDOW_DAYS_FROM_SHIP = 60. "
    "UPS publishes timing from delivery or scheduled delivery, not ship date: "
    "start a claim within 60 days of scheduled delivery "
    "(https://www.ups.com/us/en/support/file-a-claim) and file a domestic claim "
    "within nine months after delivery (UPS Tariff/Terms, Claims and Legal Action). "
    "Applying 60 days from ship date is an uncertain stand-in and is stricter than "
    "the published delivery clock."
)
_FEDEX_LOSS_SOURCE = (
    "Nine calendar months after the package was tendered to FedEx, which is the "
    "ship date. Source: FedEx Express and FedEx Ground claim-form FAQ for "
    "nondelivery claims "
    "(https://www.partnership.com/pdffiles/Hosted%20PDFs/FedExclaimsform.pdf)."
)
_FEDEX_DAMAGE_SOURCE = (
    "Named constant FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP = 21. "
    "FedEx says damage must be reported within 21 calendar days of the delivery "
    "date, with supporting documents within nine months of delivery (FedEx Express "
    "and FedEx Ground claim-form FAQ). That clock is not ship date, so this "
    "ship-date stand-in is uncertain."
)
_USPS_SOURCE = (
    "60 calendar days from the mailing date, which is the ship date. "
    "Damage may be filed immediately; loss also has a service-specific earliest "
    "day that this slice does not block. Source: USPS DMM 609.1.4 "
    "(https://pe.usps.com/text/dmm300/609.htm)."
)


@dataclass(frozen=True)
class FieldError:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class TraceRejected(Exception):
    def __init__(self, errors: list[FieldError]):
        self.errors = errors
        super().__init__("; ".join(error.message for error in errors))


@dataclass(frozen=True)
class FilingWindow:
    days: int | None
    months: int | None
    uncertain: bool
    constant_name: str | None
    source_note: str


@dataclass(frozen=True)
class ReasonRules:
    required_fields: tuple[str, ...]
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    window: FilingWindow


@dataclass(frozen=True)
class TraceDetails:
    carrier: str
    tracking_reference: str
    reason: str
    length_in: float
    width_in: float
    height_in: float
    contents_summary: str
    order_reference: str
    ship_date: date


@dataclass(frozen=True)
class AcceptedTrace:
    carrier: str
    tracking_reference: str
    reason: str
    length_in: float
    width_in: float
    height_in: float
    contents_summary: str
    order_reference: str
    ship_date: date
    window: FilingWindow
    deadline: date


def _window_days(days: int, *, uncertain: bool, constant_name: str | None, source_note: str) -> FilingWindow:
    return FilingWindow(
        days=days,
        months=None,
        uncertain=uncertain,
        constant_name=constant_name,
        source_note=source_note,
    )


def _reason_rules(window: FilingWindow, required_evidence: tuple[str, ...]) -> ReasonRules:
    optional = tuple(kind for kind in EVIDENCE_KINDS if kind not in required_evidence)
    return ReasonRules(
        required_fields=_DETAIL_FIELDS,
        required_evidence=required_evidence,
        optional_evidence=optional,
        window=window,
    )


def _carrier_rules(loss_window: FilingWindow, damage_window: FilingWindow) -> dict[str, ReasonRules]:
    return {
        "loss": _reason_rules(loss_window, ("sales_invoice",)),
        "damage": _reason_rules(damage_window, ("shipment_photo", "sales_invoice")),
    }


_UPS_WINDOW = _window_days(
    UPS_FILING_WINDOW_DAYS_FROM_SHIP,
    uncertain=True,
    constant_name="UPS_FILING_WINDOW_DAYS_FROM_SHIP",
    source_note=_UPS_SOURCE,
)
_FEDEX_LOSS_WINDOW = FilingWindow(
    days=None,
    months=FEDEX_LOSS_FILING_WINDOW_MONTHS_FROM_SHIP,
    uncertain=False,
    constant_name=None,
    source_note=_FEDEX_LOSS_SOURCE,
)
_FEDEX_DAMAGE_WINDOW = _window_days(
    FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP,
    uncertain=True,
    constant_name="FEDEX_DAMAGE_FILING_WINDOW_DAYS_FROM_SHIP",
    source_note=_FEDEX_DAMAGE_SOURCE,
)
_USPS_WINDOW = _window_days(
    USPS_FILING_WINDOW_DAYS_FROM_SHIP,
    uncertain=False,
    constant_name=None,
    source_note=_USPS_SOURCE,
)

RULES: dict[str, dict[str, ReasonRules]] = {
    "UPS": _carrier_rules(_UPS_WINDOW, _UPS_WINDOW),
    "FEDEX": _carrier_rules(_FEDEX_LOSS_WINDOW, _FEDEX_DAMAGE_WINDOW),
    "USPS": _carrier_rules(_USPS_WINDOW, _USPS_WINDOW),
}


def canonical_carrier(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = " ".join(raw.strip().lower().split())
    return _CARRIER_ALIASES.get(key)


def canonical_reason(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if key in REASONS:
        return key
    return None


def rules_for(carrier: str, reason: str) -> ReasonRules | None:
    return RULES.get(carrier, {}).get(reason)


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def filing_deadline(ship_date: date, window: FilingWindow) -> date:
    if window.months is not None:
        return add_months(ship_date, window.months)
    if window.days is None:
        raise ValueError("filing window has no duration")
    return ship_date + timedelta(days=window.days)


def _candidates(raw: str) -> list[str]:
    text = raw.strip()
    found = [text]
    url_text = text
    if "://" not in text and text.lower().startswith("www."):
        url_text = "https://" + text
    if "://" not in url_text:
        return found
    parsed = urlparse(url_text)
    lowered = {key.lower(): values for key, values in parse_qs(parsed.query).items()}
    for key in _QUERY_KEYS:
        found.extend(lowered.get(key, []))
    found.extend(part for part in parsed.path.split("/") if part)
    return found


def normalize_reference(carrier: str, raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    pattern = _REFERENCE[carrier]
    for candidate in _candidates(raw):
        compact = re.sub(r"\s+", "", candidate).upper()
        if pattern.fullmatch(compact):
            return compact
    return None


def _dimension(value: float, name: str) -> tuple[float | None, FieldError | None]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, FieldError("invalid_dimension", f"{name} must be a number of inches.")
    if not math.isfinite(number) or number <= 0:
        return None, FieldError("invalid_dimension", f"{name} must be greater than 0 inches.")
    if number > 200:
        return None, FieldError("invalid_dimension", f"{name} must be 200 inches or less.")
    return round(number, 2), None


def validate_details(details: TraceDetails, *, as_of: date) -> tuple[AcceptedTrace | None, list[FieldError]]:
    errors: list[FieldError] = []
    carrier = canonical_carrier(details.carrier)
    if carrier is None:
        errors.append(FieldError("unknown_carrier", "Carrier must be UPS, FedEx, or USPS."))
        return None, errors
    reason = canonical_reason(details.reason)
    if reason is None:
        errors.append(FieldError("invalid_reason", "Reason must be loss or damage."))
        return None, errors
    rules = rules_for(carrier, reason)
    if rules is None:
        errors.append(FieldError("unknown_carrier", "No filing rules for this carrier."))
        return None, errors

    tracking = normalize_reference(carrier, details.tracking_reference)
    if tracking is None:
        errors.append(
            FieldError(
                "invalid_reference",
                f"{carrier} would reject this tracking reference. {_REFERENCE_HINT[carrier]}",
            )
        )

    length, length_error = _dimension(details.length_in, "Length")
    width, width_error = _dimension(details.width_in, "Width")
    height, height_error = _dimension(details.height_in, "Height")
    for dim_error in (length_error, width_error, height_error):
        if dim_error is not None:
            errors.append(dim_error)

    contents = details.contents_summary.strip()
    if not contents:
        errors.append(FieldError("missing_field", "Contents summary is required."))
    elif len(contents) > 2000:
        errors.append(FieldError("missing_field", "Contents summary must be 2000 characters or less."))

    order_reference = details.order_reference.strip()
    if not order_reference:
        errors.append(FieldError("missing_field", "Order reference is required."))
    elif len(order_reference) > 128:
        errors.append(FieldError("missing_field", "Order reference must be 128 characters or less."))

    if details.ship_date is None:
        errors.append(FieldError("missing_field", "Ship date is required to measure the filing window."))
        return None, errors
    if as_of < details.ship_date:
        errors.append(FieldError("ship_date_in_future", "Ship date is in the future, so the filing window has not started."))
        return None, errors

    deadline = filing_deadline(details.ship_date, rules.window)
    if as_of > deadline:
        errors.append(
            FieldError(
                "window_closed",
                (
                    f"The {carrier} {reason} filing window closed on {deadline.isoformat()} "
                    f"(ship date {details.ship_date.isoformat()}). {rules.window.source_note}"
                ),
            )
        )

    if errors or length is None or width is None or height is None or tracking is None:
        return None, errors
    return (
        AcceptedTrace(
            carrier=carrier,
            tracking_reference=tracking,
            reason=reason,
            length_in=length,
            width_in=width,
            height_in=height,
            contents_summary=contents,
            order_reference=order_reference,
            ship_date=details.ship_date,
            window=rules.window,
            deadline=deadline,
        ),
        [],
    )


def validate_evidence(carrier: str, reason: str, present: set[str]) -> list[FieldError]:
    rules = rules_for(carrier, reason)
    if rules is None:
        return [FieldError("unknown_carrier", "No evidence rules for this carrier and reason.")]
    errors: list[FieldError] = []
    unknown = sorted(kind for kind in present if kind not in EVIDENCE_KINDS)
    for kind in unknown:
        errors.append(FieldError("invalid_evidence", f"Unknown evidence type {kind}."))
    missing = [kind for kind in rules.required_evidence if kind not in present]
    if missing:
        labels = ", ".join(kind.replace("_", " ") for kind in missing)
        errors.append(
            FieldError(
                "missing_evidence",
                f"{carrier} {reason} requires {labels}.",
            )
        )
    return errors


def rules_document() -> dict:
    by_carrier: dict[str, dict] = {}
    for carrier, reasons in RULES.items():
        by_carrier[carrier] = {}
        for reason, rule in reasons.items():
            by_carrier[carrier][reason] = {
                "required_fields": list(rule.required_fields),
                "required_evidence": list(rule.required_evidence),
                "optional_evidence": list(rule.optional_evidence),
                "filing_window": {
                    "days": rule.window.days,
                    "months": rule.window.months,
                    "uncertain": rule.window.uncertain,
                    "constant_name": rule.window.constant_name,
                    "source_note": rule.window.source_note,
                },
            }
    return {
        "carriers": list(CARRIERS),
        "reasons": list(REASONS),
        "evidence_kinds": list(EVIDENCE_KINDS),
        "email_sent_on_confirm": False,
        "by_carrier": by_carrier,
    }
