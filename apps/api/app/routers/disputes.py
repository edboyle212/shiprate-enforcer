from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, set_rls_organization
from app.models import DisputeCase, DisputeCaseEvent, DisputeDraft, DisputeDraftStatus
from app.routers.imports import require_org_id
from app.services import disputes as dispute_service

router = APIRouter()


class DisputeCaseSummary(BaseModel):
    id: UUID
    discrepancy_id: UUID
    claim_amount_minor: int
    currency_code: str
    status: str
    created_at: str


class DisputeCaseDetail(DisputeCaseSummary):
    drafts: list["DisputeDraftOut"]
    events: list["DisputeCaseEventOut"]


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


def _case_summary(row: DisputeCase) -> DisputeCaseSummary:
    return DisputeCaseSummary(
        id=row.id,
        discrepancy_id=row.discrepancy_id,
        claim_amount_minor=row.claim_amount_minor,
        currency_code=row.currency_code,
        status=row.status.value,
        created_at=row.created_at.isoformat(),
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
        .options(selectinload(DisputeCase.drafts), selectinload(DisputeCase.events))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Dispute case not found")
    drafts = sorted(row.drafts, key=lambda d: d.created_at, reverse=True)
    events = sorted(row.events, key=lambda e: e.created_at)
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
