from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, set_rls_organization
from app.models import DisputeCase, DisputeDraft, DisputeMessage
from app.auth import require_org_id, require_platform_admin
from app.auth.principal import Principal
from app.services import disputes as dispute_service
from app.services import negotiation as negotiation_service
from app.services.mail import outbound_mail_configured, outbound_mail_from_address

router = APIRouter()


class DisputeCaseSummary(BaseModel):
    id: UUID
    discrepancy_id: UUID
    claim_amount_minor: int
    currency_code: str
    status: str
    autonomy_tier: str
    fee_bps: int
    recovered_amount_minor: int | None = None
    fee_amount_minor: int | None = None
    created_at: str


class DisputeCaseDetail(DisputeCaseSummary):
    drafts: list["DisputeDraftOut"]
    events: list["DisputeCaseEventOut"]
    messages: list["DisputeMessageOut"]


class DisputeDraftOut(BaseModel):
    id: UUID
    email_subject: str
    email_body: str
    status: str
    created_at: str
    approved_at: str | None


class DisputeCaseEventOut(BaseModel):
    id: UUID
    event_type: str
    payload_json: dict
    created_at: str


class DisputeMessageOut(BaseModel):
    id: UUID
    direction: str
    email_subject: str
    email_body: str
    status: str
    round_number: int
    offered_amount_minor: int | None = None
    denied: bool = False
    created_at: str
    sent_at: str | None = None


def _case_summary(row: DisputeCase) -> DisputeCaseSummary:
    return DisputeCaseSummary(
        id=row.id,
        discrepancy_id=row.discrepancy_id,
        claim_amount_minor=row.claim_amount_minor,
        currency_code=row.currency_code,
        status=row.status.value,
        autonomy_tier=row.autonomy_tier,
        fee_bps=row.fee_bps,
        recovered_amount_minor=row.recovered_amount_minor,
        fee_amount_minor=row.fee_amount_minor,
        created_at=row.created_at.isoformat(),
    )


def _message_out(m: DisputeMessage) -> DisputeMessageOut:
    return DisputeMessageOut(
        id=m.id,
        direction=m.direction.value,
        email_subject=m.email_subject,
        email_body=m.email_body,
        status=m.status.value,
        round_number=m.round_number,
        offered_amount_minor=m.offered_amount_minor,
        denied=bool(m.denied),
        created_at=m.created_at.isoformat() if m.created_at else "",
        sent_at=m.sent_at.isoformat() if m.sent_at else None,
    )


@router.post("/discrepancies/{discrepancy_id}/open-case", response_model=DisputeCaseSummary)
async def open_case_for_discrepancy(
    discrepancy_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DisputeCaseSummary:
    await set_rls_organization(db, org_id)
    try:
        case = await dispute_service.open_dispute_case(db, organization_id=org_id, discrepancy_id=discrepancy_id)
    except ValueError as exc:
        code = str(exc)
        if code == "discrepancy_not_found":
            raise HTTPException(status_code=404, detail="Discrepancy not found") from exc
        if code == "non_positive_claim":
            raise HTTPException(status_code=400, detail="Discrepancy has no positive claim amount") from exc
        raise
    await db.commit()
    await db.refresh(case)
    return _case_summary(case)


@router.get("/dispute-cases", response_model=list[DisputeCaseSummary])
async def list_dispute_cases(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> list[DisputeCaseSummary]:
    await set_rls_organization(db, org_id)
    rows = (
        await db.scalars(
            select(DisputeCase)
            .where(DisputeCase.organization_id == org_id)
            .order_by(DisputeCase.created_at.desc())
        )
    ).all()
    return [_case_summary(row) for row in rows]


class OutboundMailStatus(BaseModel):
    configured: bool
    from_address: str | None = None


@router.get("/dispute-cases/outbound-mail", response_model=OutboundMailStatus)
async def dispute_outbound_mail_status(
    org_id: UUID = Depends(require_org_id),
) -> OutboundMailStatus:
    return OutboundMailStatus(
        configured=outbound_mail_configured(),
        from_address=outbound_mail_from_address(),
    )


@router.get("/dispute-cases/{case_id}", response_model=DisputeCaseDetail)
async def get_dispute_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DisputeCaseDetail:
    await set_rls_organization(db, org_id)
    row = await db.scalar(
        select(DisputeCase)
        .where(DisputeCase.id == case_id, DisputeCase.organization_id == org_id)
        .options(
            selectinload(DisputeCase.drafts),
            selectinload(DisputeCase.events),
            selectinload(DisputeCase.messages),
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Dispute case not found")
    drafts = sorted(row.drafts, key=lambda d: d.created_at, reverse=True)
    events = sorted(row.events, key=lambda e: e.created_at)
    messages = sorted(row.messages, key=lambda m: m.created_at)
    return DisputeCaseDetail(
        **_case_summary(row).model_dump(),
        drafts=[
            DisputeDraftOut(
                id=d.id,
                email_subject=d.email_subject,
                email_body=d.email_body,
                status=d.status.value,
                created_at=d.created_at.isoformat(),
                approved_at=d.approved_at.isoformat() if d.approved_at else None,
            )
            for d in drafts
        ],
        events=[
            DisputeCaseEventOut(
                id=e.id,
                event_type=e.event_type,
                payload_json=dict(e.payload_json or {}),
                created_at=e.created_at.isoformat(),
            )
            for e in events
        ],
        messages=[_message_out(m) for m in messages],
    )


class DraftResponse(BaseModel):
    draft: DisputeDraftOut


@router.post("/dispute-cases/{case_id}/draft", response_model=DraftResponse)
async def create_dispute_draft(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DraftResponse:
    await set_rls_organization(db, org_id)
    try:
        draft = await dispute_service.create_or_refresh_draft(
            db, organization_id=org_id, dispute_case_id=case_id
        )
    except ValueError as exc:
        if str(exc) == "case_not_found":
            raise HTTPException(status_code=404, detail="Dispute case not found") from exc
        raise
    await db.commit()
    await db.refresh(draft)
    return DraftResponse(
        draft=DisputeDraftOut(
            id=draft.id,
            email_subject=draft.email_subject,
            email_body=draft.email_body,
            status=draft.status.value,
            created_at=draft.created_at.isoformat(),
            approved_at=None,
        )
    )


class ApproveDraftRequest(BaseModel):
    draft_id: UUID | None = None


@router.post("/dispute-cases/{case_id}/approve-draft", response_model=DraftResponse)
async def approve_dispute_draft(
    case_id: UUID,
    body: ApproveDraftRequest | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DraftResponse:
    await set_rls_organization(db, org_id)
    draft_id = body.draft_id if body else None
    try:
        draft = await dispute_service.approve_draft(
            db,
            organization_id=org_id,
            dispute_case_id=case_id,
            draft_id=draft_id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "case_not_found":
            raise HTTPException(status_code=404, detail="Dispute case not found") from exc
        if code == "draft_not_found":
            raise HTTPException(status_code=404, detail="Draft not found") from exc
        raise
    await db.commit()
    await db.refresh(draft)
    return DraftResponse(
        draft=DisputeDraftOut(
            id=draft.id,
            email_subject=draft.email_subject,
            email_body=draft.email_body,
            status=draft.status.value,
            created_at=draft.created_at.isoformat(),
            approved_at=draft.approved_at.isoformat() if draft.approved_at else None,
        )
    )


class NegotiateResponse(BaseModel):
    case: DisputeCaseSummary


@router.post("/dispute-cases/{case_id}/negotiate", response_model=NegotiateResponse)
async def negotiate_dispute_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> NegotiateResponse:
    await set_rls_organization(db, org_id)
    try:
        case = await negotiation_service.run_negotiation_step(
            db, organization_id=org_id, dispute_case_id=case_id
        )
    except ValueError as exc:
        raise _negotiation_http(exc) from exc
    await db.commit()
    await db.refresh(case)
    return NegotiateResponse(case=_case_summary(case))


class ReplyRequest(BaseModel):
    subject: str
    body: str
    offered_amount_minor: int | None = None
    denied: bool = False


@router.post("/dispute-cases/{case_id}/replies", response_model=DisputeMessageOut)
async def post_carrier_reply(
    case_id: UUID,
    body: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
    _admin: Principal = Depends(require_platform_admin),
) -> DisputeMessageOut:
    await set_rls_organization(db, org_id)
    try:
        message = await negotiation_service.record_inbound_reply(
            db,
            organization_id=org_id,
            dispute_case_id=case_id,
            subject=body.subject,
            body=body.body,
            offered_amount_minor=body.offered_amount_minor,
            denied=body.denied,
        )
    except ValueError as exc:
        raise _negotiation_http(exc) from exc
    await db.commit()
    await db.refresh(message)
    return _message_out(message)


class ApproveSendRequest(BaseModel):
    message_id: UUID | None = None


@router.post("/dispute-cases/{case_id}/approve-send", response_model=DisputeMessageOut)
async def approve_send_message(
    case_id: UUID,
    body: ApproveSendRequest | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DisputeMessageOut:
    await set_rls_organization(db, org_id)
    message_id = body.message_id if body else None
    try:
        message = await negotiation_service.approve_and_send(
            db, organization_id=org_id, dispute_case_id=case_id, message_id=message_id
        )
    except ValueError as exc:
        raise _negotiation_http(exc) from exc
    await db.commit()
    await db.refresh(message)
    return _message_out(message)


@router.post("/dispute-cases/{case_id}/stop", response_model=NegotiateResponse)
async def stop_dispute_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> NegotiateResponse:
    await set_rls_organization(db, org_id)
    try:
        case = await negotiation_service.stop_case(db, organization_id=org_id, dispute_case_id=case_id)
    except ValueError as exc:
        raise _negotiation_http(exc) from exc
    await db.commit()
    await db.refresh(case)
    return NegotiateResponse(case=_case_summary(case))


class RecordCreditRequest(BaseModel):
    recovered_amount_minor: int


@router.post("/dispute-cases/{case_id}/record-credit", response_model=NegotiateResponse)
async def record_dispute_credit(
    case_id: UUID,
    body: RecordCreditRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
    _admin: Principal = Depends(require_platform_admin),
) -> NegotiateResponse:
    await set_rls_organization(db, org_id)
    try:
        case = await negotiation_service.record_credit(
            db,
            organization_id=org_id,
            dispute_case_id=case_id,
            recovered_amount_minor=body.recovered_amount_minor,
        )
    except ValueError as exc:
        raise _negotiation_http(exc) from exc
    await db.commit()
    await db.refresh(case)
    return NegotiateResponse(case=_case_summary(case))


def _negotiation_http(exc: ValueError) -> HTTPException:
    code = str(exc)
    mapping = {
        "case_not_found": (404, "Dispute case not found"),
        "message_not_found": (404, "Message not found"),
        "case_terminal": (400, "Case is already closed or credited"),
        "awaiting_platform": (400, "Case is waiting for platform credit entry"),
        "nothing_to_negotiate": (400, "Nothing to negotiate"),
        "invalid_recovered_amount": (400, "Recovered amount is invalid"),
        "recovered_exceeds_claim": (400, "Recovered amount exceeds claim"),
        "credit_incomplete": (400, "Credit is missing recovered amount or fee"),
        "mail_delivery_failed": (502, "Carrier email could not be sent — check Resend configuration"),
        "outbound_disabled": (503, "Outbound carrier email is disabled"),
        "carrier_unresolved": (400, "No verified carrier contact for this dispute"),
    }
    status, detail = mapping.get(code, (400, code))
    return HTTPException(status_code=status, detail=detail)
