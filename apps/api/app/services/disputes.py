"""Dispute case lifecycle — drafts only, no auto-send."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Discrepancy,
    DisputeCase,
    DisputeCaseEvent,
    DisputeCaseStatus,
    DisputeDraft,
    DisputeDraftStatus,
    Organization,
)
from app.services.org_settings import autonomy_tier_from_settings, recovery_fee_bps_from_settings


def format_money_minor(minor: int, currency: str) -> str:
    return f"{minor / 100:.2f} {currency}"


def build_dispute_draft_text(
    *,
    discrepancy: Discrepancy,
    claim_amount_minor: int,
    trace_summary: dict[str, Any],
    reason_codes: list[str],
) -> tuple[str, str]:
    """Deterministic email template; includes rating trace facts (no AI, no send)."""
    subject = f"Billing dispute — claim {format_money_minor(claim_amount_minor, discrepancy.currency_code)}"
    trace_lines = [
        f"- Engine version: {trace_summary.get('engine_version')}",
        f"- Zone: {trace_summary.get('zone')}",
        f"- Billable weight (oz): {trace_summary.get('billable_weight_oz')}",
        f"- Minimum charge applied: {trace_summary.get('minimum_charge_applied')}",
        f"- Rate table key: {trace_summary.get('table_key')}",
        f"- Allowed total (minor): {trace_summary.get('allowed_total_minor')}",
    ]
    body = (
        "DRAFT — not sent automatically.\n\n"
        f"We dispute the billed amount of {format_money_minor(discrepancy.billed_amount_minor, discrepancy.currency_code)} "
        f"versus allowed {format_money_minor(discrepancy.allowed_amount_minor, discrepancy.currency_code)} "
        f"(variance {format_money_minor(discrepancy.variance_minor, discrepancy.currency_code)}).\n\n"
        f"Claim amount: {format_money_minor(claim_amount_minor, discrepancy.currency_code)}\n"
        f"Reason codes: {', '.join(reason_codes)}\n\n"
        "Deterministic rating trace:\n"
        + "\n".join(trace_lines)
        + "\n\n"
        "Please review and approve this draft before any carrier submission."
    )
    return subject, body


async def open_dispute_case(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    discrepancy_id: uuid.UUID,
) -> DisputeCase:
    disc = await session.scalar(
        select(Discrepancy)
        .where(Discrepancy.id == discrepancy_id, Discrepancy.organization_id == organization_id)
        .options(selectinload(Discrepancy.dispute_case))
    )
    if not disc:
        raise ValueError("discrepancy_not_found")
    if disc.dispute_case:
        return disc.dispute_case

    claim_amount_minor = int(disc.variance_minor)
    if claim_amount_minor <= 0:
        raise ValueError("non_positive_claim")

    org = await session.scalar(select(Organization).where(Organization.id == organization_id))
    settings_json = dict(org.settings_json or {}) if org else {}

    case = DisputeCase(
        organization_id=organization_id,
        discrepancy_id=disc.id,
        claim_amount_minor=claim_amount_minor,
        currency_code=disc.currency_code,
        status=DisputeCaseStatus.open,
        autonomy_tier=autonomy_tier_from_settings(settings_json),
        fee_bps=recovery_fee_bps_from_settings(settings_json),
    )
    session.add(case)
    await session.flush()
    session.add(
        DisputeCaseEvent(
            organization_id=organization_id,
            dispute_case_id=case.id,
            event_type="case_opened",
            payload_json={
                "discrepancy_id": str(disc.id),
                "claim_amount_minor": claim_amount_minor,
            },
        )
    )
    return case


async def create_or_refresh_draft(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
) -> DisputeDraft:
    case = await session.scalar(
        select(DisputeCase)
        .where(DisputeCase.id == dispute_case_id, DisputeCase.organization_id == organization_id)
        .options(selectinload(DisputeCase.discrepancy), selectinload(DisputeCase.drafts))
    )
    if not case:
        raise ValueError("case_not_found")
    disc = case.discrepancy
    subject, body = build_dispute_draft_text(
        discrepancy=disc,
        claim_amount_minor=case.claim_amount_minor,
        trace_summary=dict(disc.trace_summary_json or {}),
        reason_codes=list(disc.reason_codes or []),
    )
    draft = DisputeDraft(
        organization_id=organization_id,
        dispute_case_id=case.id,
        email_subject=subject,
        email_body=body,
        status=DisputeDraftStatus.draft,
    )
    session.add(draft)
    await session.flush()
    session.add(
        DisputeCaseEvent(
            organization_id=organization_id,
            dispute_case_id=case.id,
            event_type="draft_created",
            payload_json={"draft_id": str(draft.id)},
        )
    )
    return draft


async def approve_draft(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    dispute_case_id: uuid.UUID,
    draft_id: uuid.UUID | None = None,
) -> DisputeDraft:
    case = await session.scalar(
        select(DisputeCase)
        .where(DisputeCase.id == dispute_case_id, DisputeCase.organization_id == organization_id)
        .options(selectinload(DisputeCase.drafts))
    )
    if not case:
        raise ValueError("case_not_found")

    draft: DisputeDraft | None = None
    if draft_id:
        draft = next((d for d in case.drafts if d.id == draft_id), None)
    else:
        open_drafts = [d for d in case.drafts if d.status == DisputeDraftStatus.draft]
        draft = max(open_drafts, key=lambda d: d.created_at) if open_drafts else None
    if not draft:
        raise ValueError("draft_not_found")

    draft.status = DisputeDraftStatus.approved
    draft.approved_at = datetime.now(UTC)
    session.add(
        DisputeCaseEvent(
            organization_id=organization_id,
            dispute_case_id=case.id,
            event_type="draft_approved",
            payload_json={"draft_id": str(draft.id), "sent": False},
        )
    )
    return draft
