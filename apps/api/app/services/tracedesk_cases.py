"""TraceDesk orders, organization carrier contacts, and claim packets.

Confirm stores a case and a packet. It does not send email.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OrganizationCarrierContact,
    TraceDeskCase,
    TraceDeskClaimPacket,
    TraceDeskEvidence,
    TraceDeskOrder,
    TraceDeskOrderImport,
)
from app.services.storage import storage_service
from app.services.tracedesk_rules import (
    EVIDENCE_KINDS,
    AcceptedTrace,
    FieldError,
    TraceDetails,
    TraceRejected,
    canonical_carrier,
    validate_details,
    validate_evidence,
)

MAX_EVIDENCE_BYTES = 8_000_000
_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_INVOICE_TYPES = _PHOTO_TYPES | {"application/pdf"}
_EXT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SHIP_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ORDER_HEADERS = (
    "order_id",
    "customer_name",
    "customer_email",
    "carrier",
    "tracking_reference",
    "ship_date",
)
_CONTACT_HEADERS = ("carrier", "contact_name", "email", "account_reference")
_LIVE_STATUSES = frozenset({"open", "needs_attention"})


@dataclass(frozen=True)
class EvidenceFile:
    kind: str
    filename: str
    content_type: str | None
    data: bytes


@dataclass(frozen=True)
class EvidenceName:
    kind: str
    filename: str


@dataclass(frozen=True)
class ParsedOrder:
    external_order_id: str
    customer_name: str
    customer_email: str
    carrier_code: str
    tracking_reference: str
    ship_date: date


@dataclass(frozen=True)
class ParsedContact:
    carrier_code: str
    contact_name: str
    email: str
    account_reference: str | None


@dataclass
class CsvParse:
    orders: list[ParsedOrder]
    contacts: list[ParsedContact]
    errors: list[dict[str, object]]
    header_error: bool = False


@dataclass
class QueueRow:
    id: uuid.UUID
    external_order_id: str
    customer_name: str
    customer_email: str
    carrier_code: str
    tracking_reference: str
    ship_date: date
    case_id: uuid.UUID | None
    case_status: str | None


def _header_map(fieldnames: list[str] | None) -> dict[str, str]:
    return {(name or "").strip().lower(): name for name in (fieldnames or []) if name is not None}


def _row_error(row_number: int, message: str) -> dict[str, object]:
    return {"row": row_number, "message": message}


def parse_order_csv(text: str) -> CsvParse:
    if not text.strip():
        return CsvParse([], [], [_row_error(0, "CSV is empty.")], header_error=True)
    reader = csv.DictReader(io.StringIO(text))
    headers = _header_map(list(reader.fieldnames or []))
    missing = [name for name in _ORDER_HEADERS if name not in headers]
    if missing:
        return CsvParse(
            [],
            [],
            [_row_error(1, "Missing columns: " + ", ".join(missing) + ".")],
            header_error=True,
        )
    orders: list[ParsedOrder] = []
    errors: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, row in enumerate(reader, start=2):
        values = {key: (row.get(headers[key]) or "").strip() for key in _ORDER_HEADERS}
        if not any(values.values()):
            continue
        if not values["order_id"]:
            errors.append(_row_error(index, "Order id is required."))
            continue
        if values["order_id"] in seen:
            errors.append(_row_error(index, f"Duplicate order id {values['order_id']} in this file."))
            continue
        if not values["customer_name"]:
            errors.append(_row_error(index, "Customer name is required."))
            continue
        if not _EMAIL.fullmatch(values["customer_email"]):
            errors.append(_row_error(index, "Customer email is not a valid email address."))
            continue
        carrier = canonical_carrier(values["carrier"])
        if carrier is None:
            errors.append(_row_error(index, "Carrier must be UPS, FedEx, or USPS."))
            continue
        if not values["tracking_reference"]:
            errors.append(_row_error(index, "Tracking reference is required."))
            continue
        if not _SHIP_DATE.fullmatch(values["ship_date"]):
            errors.append(_row_error(index, "Ship date must be YYYY-MM-DD."))
            continue
        try:
            ship_date = date.fromisoformat(values["ship_date"])
        except ValueError:
            errors.append(_row_error(index, "Ship date is not a real calendar date."))
            continue
        seen.add(values["order_id"])
        orders.append(
            ParsedOrder(
                external_order_id=values["order_id"],
                customer_name=values["customer_name"],
                customer_email=values["customer_email"].lower(),
                carrier_code=carrier,
                tracking_reference=values["tracking_reference"],
                ship_date=ship_date,
            )
        )
    return CsvParse(orders, [], errors, header_error=False)


def parse_contact_csv(text: str) -> CsvParse:
    if not text.strip():
        return CsvParse([], [], [_row_error(0, "CSV is empty.")], header_error=True)
    reader = csv.DictReader(io.StringIO(text))
    headers = _header_map(list(reader.fieldnames or []))
    missing = [name for name in _CONTACT_HEADERS if name not in headers]
    if missing:
        return CsvParse(
            [],
            [],
            [_row_error(1, "Missing columns: " + ", ".join(missing) + ".")],
            header_error=True,
        )
    contacts: list[ParsedContact] = []
    errors: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, row in enumerate(reader, start=2):
        values = {key: (row.get(headers[key]) or "").strip() for key in _CONTACT_HEADERS}
        if not any(values.values()):
            continue
        carrier = canonical_carrier(values["carrier"])
        if carrier is None:
            errors.append(_row_error(index, "Carrier must be UPS, FedEx, or USPS."))
            continue
        if carrier in seen:
            errors.append(_row_error(index, f"Duplicate {carrier} contact in this file."))
            continue
        if not values["contact_name"]:
            errors.append(_row_error(index, "Contact name is required."))
            continue
        if len(values["contact_name"]) > 255:
            errors.append(_row_error(index, "Contact name must be 255 characters or less."))
            continue
        if not _EMAIL.fullmatch(values["email"]):
            errors.append(_row_error(index, "Contact email is not a valid email address."))
            continue
        account = values["account_reference"] or None
        if account is not None and len(account) > 128:
            errors.append(_row_error(index, "Account reference must be 128 characters or less."))
            continue
        seen.add(carrier)
        contacts.append(
            ParsedContact(
                carrier_code=carrier,
                contact_name=values["contact_name"],
                email=values["email"].lower(),
                account_reference=account,
            )
        )
    return CsvParse([], contacts, errors, header_error=False)


def _decode_csv(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TraceRejected([FieldError("invalid_csv", "CSV must be UTF-8.")]) from exc


async def import_order_csv(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> dict:
    if not data:
        raise TraceRejected([FieldError("invalid_csv", "CSV is empty.")])
    parsed = parse_order_csv(_decode_csv(data))
    if parsed.header_error:
        raise TraceRejected([FieldError("invalid_csv", str(error["message"])) for error in parsed.errors])
    key, digest = storage_service.put_immutable(str(organization_id), filename or "orders.csv", data)
    record = TraceDeskOrderImport(
        id=uuid.uuid4(),
        organization_id=organization_id,
        original_filename=filename or "orders.csv",
        sha256_hex=digest,
        storage_key=key,
        storage_backend=storage_service.backend_name,
    )
    session.add(record)
    await session.flush()
    created = 0
    skipped = 0
    for row in parsed.orders:
        existing = await session.scalar(
            select(TraceDeskOrder.id).where(
                TraceDeskOrder.organization_id == organization_id,
                TraceDeskOrder.external_order_id == row.external_order_id,
            )
        )
        if existing is not None:
            skipped += 1
            continue
        session.add(
            TraceDeskOrder(
                id=uuid.uuid4(),
                organization_id=organization_id,
                import_id=record.id,
                external_order_id=row.external_order_id,
                customer_name=row.customer_name,
                customer_email=row.customer_email,
                carrier_code=row.carrier_code,
                tracking_reference=row.tracking_reference,
                ship_date=row.ship_date,
            )
        )
        created += 1
    await session.commit()
    return {
        "import_id": str(record.id),
        "created": created,
        "skipped": skipped,
        "errors": parsed.errors,
    }


async def import_contact_csv(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> dict:
    if not data:
        raise TraceRejected([FieldError("invalid_csv", "CSV is empty.")])
    parsed = parse_contact_csv(_decode_csv(data))
    if parsed.header_error:
        raise TraceRejected([FieldError("invalid_csv", str(error["message"])) for error in parsed.errors])
    key, digest = storage_service.put_immutable(str(organization_id), filename or "contacts.csv", data)
    created = 0
    updated = 0
    for row in parsed.contacts:
        existing = await session.scalar(
            select(OrganizationCarrierContact).where(
                OrganizationCarrierContact.organization_id == organization_id,
                OrganizationCarrierContact.carrier_code == row.carrier_code,
            )
        )
        if existing is None:
            session.add(
                OrganizationCarrierContact(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    carrier_code=row.carrier_code,
                    contact_name=row.contact_name,
                    email=row.email,
                    account_reference=row.account_reference,
                )
            )
            created += 1
        else:
            existing.contact_name = row.contact_name
            existing.email = row.email
            existing.account_reference = row.account_reference
            updated += 1
    await session.commit()
    return {
        "created": created,
        "updated": updated,
        "errors": parsed.errors,
        "stored_file": {"storage_key": key, "sha256_hex": digest},
    }


def contact_payload(contact: OrganizationCarrierContact) -> dict:
    return {
        "id": str(contact.id),
        "carrier_code": contact.carrier_code,
        "contact_name": contact.contact_name,
        "email": contact.email,
        "account_reference": contact.account_reference,
    }


async def list_contacts(session: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    rows = (
        await session.scalars(
            select(OrganizationCarrierContact)
            .where(OrganizationCarrierContact.organization_id == organization_id)
            .order_by(OrganizationCarrierContact.carrier_code)
        )
    ).all()
    return [contact_payload(row) for row in rows]


async def load_org_contact(
    session: AsyncSession,
    organization_id: uuid.UUID,
    carrier_code: str,
) -> OrganizationCarrierContact | None:
    return await session.scalar(
        select(OrganizationCarrierContact).where(
            OrganizationCarrierContact.organization_id == organization_id,
            OrganizationCarrierContact.carrier_code == carrier_code,
        )
    )


def build_queue_rows(orders: list[TraceDeskOrder], cases: list[TraceDeskCase]) -> list[QueueRow]:
    by_order = {case.order_id: case for case in cases}
    rows: list[QueueRow] = []
    for order in orders:
        case = by_order.get(order.id)
        rows.append(
            QueueRow(
                id=order.id,
                external_order_id=order.external_order_id,
                customer_name=order.customer_name,
                customer_email=order.customer_email,
                carrier_code=order.carrier_code,
                tracking_reference=order.tracking_reference,
                ship_date=order.ship_date,
                case_id=None if case is None else case.id,
                case_status=None if case is None else case.status,
            )
        )
    rows.sort(key=lambda row: (row.ship_date, row.external_order_id), reverse=True)
    return rows


def summarize_counts(rows: list[QueueRow]) -> dict[str, int]:
    return {
        "ready_to_review": sum(1 for row in rows if row.case_status is None),
        "live_investigations": sum(1 for row in rows if row.case_status in _LIVE_STATUSES),
        "awaiting_carrier": sum(1 for row in rows if row.case_status == "awaiting_carrier"),
    }


def filter_rows(rows: list[QueueRow], query: str | None) -> list[QueueRow]:
    if query is None or not query.strip():
        return rows
    needle = query.strip().lower()
    return [
        row
        for row in rows
        if needle in row.external_order_id.lower()
        or needle in row.customer_name.lower()
        or needle in row.customer_email.lower()
    ]


def _row_payload(row: QueueRow) -> dict:
    return {
        "id": str(row.id),
        "external_order_id": row.external_order_id,
        "customer_name": row.customer_name,
        "customer_email": row.customer_email,
        "carrier_code": row.carrier_code,
        "tracking_reference": row.tracking_reference,
        "ship_date": row.ship_date.isoformat(),
        "case_id": None if row.case_id is None else str(row.case_id),
        "case_status": row.case_status,
    }


async def list_queue(session: AsyncSession, organization_id: uuid.UUID, query: str | None) -> dict:
    orders = (
        await session.scalars(select(TraceDeskOrder).where(TraceDeskOrder.organization_id == organization_id))
    ).all()
    cases = (
        await session.scalars(select(TraceDeskCase).where(TraceDeskCase.organization_id == organization_id))
    ).all()
    rows = build_queue_rows(list(orders), list(cases))
    counts = summarize_counts(rows)
    shown = filter_rows(rows, query)
    return {"counts": counts, "orders": [_row_payload(row) for row in shown]}


def build_claim_email(
    *,
    accepted: AcceptedTrace,
    evidence: list[EvidenceName],
    contact: OrganizationCarrierContact,
) -> tuple[str, str]:
    evidence_lines = [f"- {item.kind.replace('_', ' ')}: {item.filename}" for item in sorted(evidence, key=lambda item: (item.kind, item.filename))]
    if not evidence_lines:
        evidence_lines = ["- none attached"]
    account = contact.account_reference or "none"
    subject = f"Trace {accepted.order_reference} / {accepted.tracking_reference} / {accepted.reason}"
    body = "\n".join(
        [
            "TraceDesk claim packet",
            "This email was not sent.",
            "",
            f"Carrier: {accepted.carrier}",
            f"Order: {accepted.order_reference}",
            f"Tracking: {accepted.tracking_reference}",
            f"Reason: {accepted.reason}",
            f"Ship date: {accepted.ship_date.isoformat()}",
            f"Dimensions (in): {accepted.length_in:g} x {accepted.width_in:g} x {accepted.height_in:g}",
            f"Contents: {accepted.contents_summary}",
            "",
            "Evidence:",
            *evidence_lines,
            "",
            f"Recipient: {contact.contact_name} <{contact.email}>",
            f"Account reference: {account}",
        ]
    )
    return subject, body


def _resolved_content_type(filename: str, content_type: str | None) -> str | None:
    if content_type:
        base = content_type.split(";")[0].strip().lower()
        if base and base != "application/octet-stream":
            return base
    return _EXT_TYPES.get(Path(filename).suffix.lower())


def _allowed_types(kind: str) -> set[str]:
    if kind == "shipment_photo":
        return _PHOTO_TYPES
    return _INVOICE_TYPES


def inspect_evidence_files(files: list[EvidenceFile]) -> tuple[list[EvidenceFile], list[FieldError]]:
    errors: list[FieldError] = []
    kept: list[EvidenceFile] = []
    seen: set[str] = set()
    for item in files:
        if item.kind not in EVIDENCE_KINDS:
            errors.append(FieldError("invalid_evidence", f"Unknown evidence type {item.kind}."))
            continue
        if item.kind in seen:
            errors.append(FieldError("invalid_evidence", f"Only one {item.kind.replace('_', ' ')} can be attached."))
            continue
        if not item.data:
            continue
        seen.add(item.kind)
        if len(item.data) > MAX_EVIDENCE_BYTES:
            errors.append(FieldError("invalid_evidence", f"{item.filename} is larger than 8 MB."))
            continue
        content_type = _resolved_content_type(item.filename, item.content_type)
        if content_type not in _allowed_types(item.kind):
            errors.append(
                FieldError(
                    "invalid_evidence",
                    f"{item.filename} must be a photo" if item.kind == "shipment_photo" else f"{item.filename} must be a photo or PDF.",
                )
            )
            continue
        kept.append(
            EvidenceFile(
                kind=item.kind,
                filename=Path(item.filename).name or item.kind,
                content_type=content_type,
                data=item.data,
            )
        )
    return kept, errors


def _missing_contact(carrier: str) -> FieldError:
    return FieldError(
        "missing_carrier_contact",
        f"Upload a {carrier} contact for this organization before saving the trace.",
    )


def preview_trace(
    *,
    order: TraceDeskOrder,
    contact: OrganizationCarrierContact | None,
    tracking_reference: str,
    reason: str,
    length_in: float,
    width_in: float,
    height_in: float,
    contents_summary: str,
    order_reference: str,
    evidence: list[EvidenceName],
    as_of: date,
    require_contact: bool,
) -> dict:
    carrier = canonical_carrier(order.carrier_code)
    if carrier is None:
        raise TraceRejected([FieldError("unknown_carrier", "Carrier must be UPS, FedEx, or USPS.")])
    if order.ship_date is None:
        raise TraceRejected([FieldError("missing_field", "Ship date is required to measure the filing window.")])
    accepted, errors = validate_details(
        TraceDetails(
            carrier=carrier,
            tracking_reference=tracking_reference,
            reason=reason,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            contents_summary=contents_summary,
            order_reference=order_reference,
            ship_date=order.ship_date,
        ),
        as_of=as_of,
    )
    if require_contact:
        errors.extend(validate_evidence(carrier, reason if accepted is None else accepted.reason, {item.kind for item in evidence}))
        if contact is None or canonical_carrier(contact.carrier_code) != carrier:
            errors.append(_missing_contact(carrier))
    if errors or accepted is None:
        raise TraceRejected(errors or [FieldError("invalid_details", "Trace details are incomplete.")])
    recipient = None if contact is None else contact_payload(contact)
    subject = None
    body = None
    if contact is not None and canonical_carrier(contact.carrier_code) == carrier:
        subject, body = build_claim_email(accepted=accepted, evidence=evidence, contact=contact)
    return {
        "ok": True,
        "email_subject": subject,
        "email_body": body,
        "email_sent": False,
        "normalized_tracking": accepted.tracking_reference,
        "filing_deadline": accepted.deadline.isoformat(),
        "filing_window_source": accepted.window.source_note,
        "filing_window_uncertain": accepted.window.uncertain,
        "recipient": recipient,
        "contact_ready": recipient is not None,
    }


async def create_trace_case(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    order: TraceDeskOrder,
    tracking_reference: str,
    reason: str,
    length_in: float,
    width_in: float,
    height_in: float,
    contents_summary: str,
    order_reference: str,
    evidence_files: list[EvidenceFile],
    as_of: date | None = None,
) -> dict:
    if order.organization_id != organization_id:
        raise TraceRejected([FieldError("wrong_organization", "Order is not in this organization.")])
    today = date.today() if as_of is None else as_of
    carrier = canonical_carrier(order.carrier_code)
    if carrier is None:
        raise TraceRejected([FieldError("unknown_carrier", "Carrier must be UPS, FedEx, or USPS.")])
    contact = await load_org_contact(session, organization_id, carrier)
    contact_errors = [] if contact is not None else [_missing_contact(carrier)]
    existing = await session.scalar(
        select(TraceDeskCase.id).where(
            TraceDeskCase.organization_id == organization_id,
            TraceDeskCase.order_id == order.id,
        )
    )
    if existing is not None:
        raise TraceRejected([FieldError("case_exists", "This order already has a trace.")])
    if order.ship_date is None:
        raise TraceRejected([FieldError("missing_field", "Ship date is required to measure the filing window.")])

    accepted, detail_errors = validate_details(
        TraceDetails(
            carrier=carrier,
            tracking_reference=tracking_reference,
            reason=reason,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            contents_summary=contents_summary,
            order_reference=order_reference,
            ship_date=order.ship_date,
        ),
        as_of=today,
    )
    kept, file_errors = inspect_evidence_files(evidence_files)
    evidence_errors = validate_evidence(
        carrier,
        accepted.reason if accepted is not None else (reason or "").strip().lower(),
        {item.kind for item in kept},
    )
    errors = [*contact_errors, *detail_errors, *file_errors, *evidence_errors]
    if errors or accepted is None or contact is None:
        raise TraceRejected(errors or [FieldError("invalid_details", "Trace details are incomplete.")])

    names = [EvidenceName(item.kind, item.filename) for item in kept]
    subject, body = build_claim_email(accepted=accepted, evidence=names, contact=contact)
    stored: list[dict] = []
    for item in kept:
        key, digest = storage_service.put_immutable(str(organization_id), item.filename, item.data)
        stored.append(
            {
                "kind": item.kind,
                "filename": item.filename,
                "content_type": item.content_type,
                "byte_size": len(item.data),
                "sha256_hex": digest,
                "storage_key": key,
                "storage_backend": storage_service.backend_name,
            }
        )

    case_id = uuid.uuid4()
    case = TraceDeskCase(
        id=case_id,
        organization_id=organization_id,
        order_id=order.id,
        carrier_code=accepted.carrier,
        tracking_reference=accepted.tracking_reference,
        reason=accepted.reason,
        length_in=accepted.length_in,
        width_in=accepted.width_in,
        height_in=accepted.height_in,
        contents_summary=accepted.contents_summary,
        order_reference=accepted.order_reference,
        ship_date=accepted.ship_date,
        status="open",
    )
    session.add(case)
    await session.flush()
    for item in stored:
        session.add(
            TraceDeskEvidence(
                id=uuid.uuid4(),
                organization_id=organization_id,
                case_id=case_id,
                kind=item["kind"],
                original_filename=item["filename"],
                content_type=item["content_type"],
                byte_size=item["byte_size"],
                sha256_hex=item["sha256_hex"],
                storage_key=item["storage_key"],
                storage_backend=item["storage_backend"],
            )
        )
    details = {
        "carrier": accepted.carrier,
        "tracking_reference": accepted.tracking_reference,
        "reason": accepted.reason,
        "length_in": accepted.length_in,
        "width_in": accepted.width_in,
        "height_in": accepted.height_in,
        "dimension_unit": "in",
        "contents_summary": accepted.contents_summary,
        "order_reference": accepted.order_reference,
        "order_id": order.external_order_id,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "ship_date": accepted.ship_date.isoformat(),
        "filing_deadline": accepted.deadline.isoformat(),
        "filing_window_source": accepted.window.source_note,
        "filing_window_uncertain": accepted.window.uncertain,
        "filing_window_constant": accepted.window.constant_name,
        "recipient": contact_payload(contact),
    }
    evidence_refs = [
        {
            "kind": item["kind"],
            "filename": item["filename"],
            "sha256_hex": item["sha256_hex"],
            "storage_key": item["storage_key"],
        }
        for item in stored
    ]
    packet = TraceDeskClaimPacket(
        id=uuid.uuid4(),
        organization_id=organization_id,
        case_id=case_id,
        details_json=details,
        evidence_json=evidence_refs,
        email_subject=subject,
        email_body=body,
        recipient_label=contact.contact_name,
        recipient_address=contact.email,
        email_sent=False,
        channel="claim_packet",
    )
    session.add(packet)
    await session.commit()
    return {
        "case_id": str(case_id),
        "status": "open",
        "email_sent": False,
        "packet": {
            "id": str(packet.id),
            "details": details,
            "evidence": evidence_refs,
            "email_subject": subject,
            "email_body": body,
            "recipient": {
                "contact_name": contact.contact_name,
                "email": contact.email,
                "account_reference": contact.account_reference,
                "carrier_code": contact.carrier_code,
            },
            "email_sent": False,
            "channel": "claim_packet",
        },
    }
