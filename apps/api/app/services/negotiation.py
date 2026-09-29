"""One-step carrier negotiation. Claim amount, fee rate, and rating trace stay fixed."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    DisputeCase,
    DisputeCaseEvent,
    DisputeCaseStatus,
    DisputeDraft,
    DisputeDraftStatus,
    DisputeMessage,
    DisputeMessageDirection,
    DisputeMessageStatus,
    Organization,
)
from app.services.disputes import build_dispute_draft_text
from app.config import settings as app_settings
from app.services.mail import (
    MailDeliveryError,
    MailSender,
    default_mail_sender,
    get_mail_sender,
    outbound_mail_configured,
)
from app.services.carrier_contacts import resolve_carrier_email

MAX_ROUNDS = 5
TERMINAL_STATUSES = frozenset({DisputeCaseStatus.credited, DisputeCaseStatus.closed})
OPEN_DISPUTE_STATUSES = frozenset(
    {
        DisputeCaseStatus.open,
        DisputeCaseStatus.awaiting_approval,
        DisputeCaseStatus.awaiting_carrier,
        DisputeCaseStatus.awaiting_platform,
    }
)


def fee_amount_minor(*, recovered_amount_minor: int, fee_bps: int) -> int:
    return recovered_amount_minor * fee_bps // 10_000


def should_send_outbound(autonomy_tier: str) -> bool:
    return autonomy_tier == "autonomous"


def outbound_round_count(messages: list[DisputeMessage]) -> int:
    return sum(1 for m in messages if m.direction == DisputeMessageDirection.outbound)


def latest_unanswered_inbound(messages: list[DisputeMessage]) -> DisputeMessage | None:
    ordered = sorted(messages, key=lambda m: m.created_at or datetime.min.replace(tzinfo=UTC))
    last_in: DisputeMessage | None = None
    for msg in ordered:
        if msg.direction == DisputeMessageDirection.inbound:
            last_in = msg
        elif msg.direction == DisputeMessageDirection.outbound and last_in is not None:
            last_in = None
    return last_in


def classify_carrier_reply(
    *,
    denied: bool,
    offered_amount_minor: int | None,
    claim_amount_minor: int,
) -> str:
    if denied:
        return "platform"
    if offered_amount_minor is None:
        return "counter"
    if offered_amount_minor >= claim_amount_minor:
        return "full_credit"
    return "platform"


def can_run_step(case: DisputeCase) -> str | None:
    if case.status in TERMINAL_STATUSES:
        return "terminal"
    if case.status == DisputeCaseStatus.awaiting_platform:
        return "awaiting_platform"
    if outbound_round_count(list(case.messages or [])) >= MAX_ROUNDS:
        return "max_rounds"
    return None


async def _load_case(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
) -> DisputeCase | None:
    return await session.scalar(
        select(DisputeCase)
        .where(DisputeCase.id == dispute_case_id, DisputeCase.organization_id == organization_id)
        .options(
            selectinload(DisputeCase.discrepancy),
            selectinload(DisputeCase.drafts),
            selectinload(DisputeCase.events),
            selectinload(DisputeCase.messages),
        )
    )


def _add_event(
    session: AsyncSession,
    case: DisputeCase,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    event = DisputeCaseEvent(
        organization_id=case.organization_id,
        dispute_case_id=case.id,
        event_type=event_type,
        payload_json=payload,
    )
    session.add(event)
    if case.events is not None:
        case.events.append(event)


def _compose_outbound_text(case: DisputeCase, *, counter: bool) -> tuple[str, str]:
    disc = case.discrepancy
    subject, body = build_dispute_draft_text(
        discrepancy=disc,
        claim_amount_minor=case.claim_amount_minor,
        trace_summary=dict(disc.trace_summary_json or {}),
        reason_codes=list(disc.reason_codes or []),
    )
    if counter:
        subject = f"RE: {subject}"
        body = "DRAFT counter — claim amount is unchanged.\n\n" + body
    return subject, body


def _send_message(
    *,
    case: DisputeCase,
    message: DisputeMessage,
    sender: MailSender,
    to_address: str | None,
) -> None:
    if not app_settings.outbound_carrier_send_enabled:
        raise ValueError("outbound_disabled")
    if not to_address:
        raise ValueError("carrier_unresolved")
    reply_to = app_settings.dispute_reply_to or app_settings.dispute_from_email
    try:
        sender.send(
            to_address=to_address,
            subject=message.email_subject,
            body=message.email_body,
            reply_to=reply_to,
        )
    except MailDeliveryError as exc:
        raise ValueError("mail_delivery_failed") from exc
    if outbound_mail_configured():
        message.status = DisputeMessageStatus.sent
        message.sent_at = datetime.now(UTC)


def apply_credit(case: DisputeCase, *, recovered_amount_minor: int) -> None:
    if recovered_amount_minor < 0:
        raise ValueError("invalid_recovered_amount")
    if recovered_amount_minor > case.claim_amount_minor:
        raise ValueError("recovered_exceeds_claim")
    case.recovered_amount_minor = recovered_amount_minor
    case.fee_amount_minor = fee_amount_minor(
        recovered_amount_minor=recovered_amount_minor, fee_bps=case.fee_bps
    )
    if case.recovered_amount_minor is None or case.fee_amount_minor is None:
        raise ValueError("credit_incomplete")
    case.status = DisputeCaseStatus.credited


def _create_outbound(
    session: AsyncSession,
    case: DisputeCase,
    *,
    sender: MailSender,
    to_address: str | None,
    counter: bool,
) -> DisputeMessage:
    next_round = outbound_round_count(list(case.messages or [])) + 1
    subject, body = _compose_outbound_text(case, counter=counter)
    message = DisputeMessage(
        organization_id=case.organization_id,
        dispute_case_id=case.id,
        direction=DisputeMessageDirection.outbound,
        email_subject=subject,
        email_body=body,
        status=DisputeMessageStatus.draft,
        round_number=next_round,
        created_at=datetime.now(UTC),
    )
    session.add(message)
    if case.messages is not None:
        case.messages.append(message)

    draft = DisputeDraft(
        organization_id=case.organization_id,
        dispute_case_id=case.id,
        email_subject=subject,
        email_body=body,
        status=DisputeDraftStatus.draft,
    )
    session.add(draft)
    if case.drafts is not None:
        case.drafts.append(draft)

    if should_send_outbound(case.autonomy_tier):
        _send_message(case=case, message=message, sender=sender, to_address=to_address)
        case.status = DisputeCaseStatus.awaiting_carrier
        _add_event(
            session,
            case,
            "message_sent",
            {"round_number": next_round, "autonomy_tier": case.autonomy_tier},
        )
    else:
        case.status = DisputeCaseStatus.awaiting_approval
        _add_event(
            session,
            case,
            "message_drafted",
            {"round_number": next_round, "autonomy_tier": case.autonomy_tier, "sent": False},
        )
    return message


async def apply_negotiation_step(
    session: AsyncSession,
    case: DisputeCase,
    *,
    org_settings: dict[str, Any] | None,
    sender: MailSender | None = None,
) -> DisputeCase:
    mail = sender or get_mail_sender()
    block = can_run_step(case)
    if block == "terminal":
        raise ValueError("case_terminal")
    if block == "awaiting_platform":
        raise ValueError("awaiting_platform")
    if block == "max_rounds":
        case.status = DisputeCaseStatus.closed
        _add_event(session, case, "stopped", {"reason": "max_rounds"})
        return case

    carrier_code = None
    if case.discrepancy and case.discrepancy.trace_summary_json:
        carrier_code = case.discrepancy.trace_summary_json.get("carrier_code")
    carrier_key = carrier_code if isinstance(carrier_code, str) else None
    to_address = await resolve_carrier_email(session, carrier_key)

    inbound = latest_unanswered_inbound(list(case.messages or []))
    if inbound is not None:
        outcome = classify_carrier_reply(
            denied=bool(inbound.denied),
            offered_amount_minor=inbound.offered_amount_minor,
            claim_amount_minor=case.claim_amount_minor,
        )
        if outcome in {"full_credit", "platform"}:
            case.status = DisputeCaseStatus.awaiting_platform
            _add_event(
                session,
                case,
                "awaiting_platform",
                {
                    "denied": bool(inbound.denied),
                    "offered_amount_minor": inbound.offered_amount_minor,
                },
            )
            return case
        _create_outbound(session, case, sender=mail, to_address=to_address, counter=True)
        return case

    if outbound_round_count(list(case.messages or [])) == 0:
        _create_outbound(session, case, sender=mail, to_address=to_address, counter=False)
        return case

    raise ValueError("nothing_to_negotiate")


async def run_negotiation_step(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
    sender: MailSender | None = None,
) -> DisputeCase:
    case = await _load_case(session, organization_id=organization_id, dispute_case_id=dispute_case_id)
    if not case:
        raise ValueError("case_not_found")
    org = await session.scalar(select(Organization).where(Organization.id == organization_id))
    settings_json = dict(org.settings_json or {}) if org else {}
    await session.flush()
    return await apply_negotiation_step(session, case, org_settings=settings_json, sender=sender)


async def record_inbound_reply(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
    subject: str,
    body: str,
    offered_amount_minor: int | None = None,
    denied: bool = False,
    sender: MailSender | None = None,
) -> DisputeMessage:
    case = await _load_case(session, organization_id=organization_id, dispute_case_id=dispute_case_id)
    if not case:
        raise ValueError("case_not_found")
    if case.status in TERMINAL_STATUSES:
        raise ValueError("case_terminal")
    message = DisputeMessage(
        organization_id=organization_id,
        dispute_case_id=case.id,
        direction=DisputeMessageDirection.inbound,
        email_subject=subject,
        email_body=body,
        status=DisputeMessageStatus.sent,
        round_number=outbound_round_count(list(case.messages or [])),
        offered_amount_minor=offered_amount_minor,
        denied=denied,
        created_at=datetime.now(UTC),
    )
    session.add(message)
    if case.messages is not None:
        case.messages.append(message)
    _add_event(
        session,
        case,
        "reply_received",
        {"offered_amount_minor": offered_amount_minor, "denied": denied},
    )
    org = await session.scalar(select(Organization).where(Organization.id == organization_id))
    settings_json = dict(org.settings_json or {}) if org else {}
    try:
        await apply_negotiation_step(
            session, case, org_settings=settings_json, sender=sender or get_mail_sender()
        )
    except ValueError as exc:
        if str(exc) not in {"nothing_to_negotiate", "awaiting_platform", "case_terminal"}:
            raise
    return message


async def approve_and_send(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
    message_id: uuid.UUID | None = None,
    sender: MailSender | None = None,
) -> DisputeMessage:
    case = await _load_case(session, organization_id=organization_id, dispute_case_id=dispute_case_id)
    if not case:
        raise ValueError("case_not_found")
    outbound = [m for m in (case.messages or []) if m.direction == DisputeMessageDirection.outbound]
    if message_id:
        message = next((m for m in outbound if m.id == message_id), None)
    else:
        pending = [m for m in outbound if m.status != DisputeMessageStatus.sent]
        message = max(pending, key=lambda m: m.created_at or datetime.min.replace(tzinfo=UTC), default=None)
    if not message:
        raise ValueError("message_not_found")
    org = await session.scalar(select(Organization).where(Organization.id == organization_id))
    settings_json = dict(org.settings_json or {}) if org else {}
    carrier_code = None
    if case.discrepancy and case.discrepancy.trace_summary_json:
        carrier_code = case.discrepancy.trace_summary_json.get("carrier_code")
    carrier_key = carrier_code if isinstance(carrier_code, str) else None
    to_address = await resolve_carrier_email(session, carrier_key)
    message.status = DisputeMessageStatus.approved
    _send_message(case=case, message=message, sender=sender or get_mail_sender(), to_address=to_address)
    case.status = DisputeCaseStatus.awaiting_carrier
    _add_event(
        session,
        case,
        "message_sent",
        {
            "message_id": str(message.id),
            "autonomy_tier": case.autonomy_tier,
            "manual": case.autonomy_tier == "draft",
        },
    )
    return message


async def stop_case(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
) -> DisputeCase:
    case = await _load_case(session, organization_id=organization_id, dispute_case_id=dispute_case_id)
    if not case:
        raise ValueError("case_not_found")
    if case.status == DisputeCaseStatus.credited:
        raise ValueError("case_terminal")
    case.status = DisputeCaseStatus.closed
    _add_event(session, case, "stopped", {"reason": "human_stop"})
    return case


async def record_credit(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
    recovered_amount_minor: int,
) -> DisputeCase:
    case = await _load_case(session, organization_id=organization_id, dispute_case_id=dispute_case_id)
    if not case:
        raise ValueError("case_not_found")
    if case.status in TERMINAL_STATUSES:
        raise ValueError("case_terminal")
    apply_credit(case, recovered_amount_minor=recovered_amount_minor)
    _add_event(
        session,
        case,
        "credited",
        {
            "recovered_amount_minor": case.recovered_amount_minor,
            "fee_amount_minor": case.fee_amount_minor,
            "source": "platform",
        },
    )
    return case
