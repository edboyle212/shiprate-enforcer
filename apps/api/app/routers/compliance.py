from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, set_rls_organization
from app.models import Discrepancy, DiscrepancyEvent, DiscrepancyReviewStatus
from app.routers.imports import require_org_id
from app.services.compliance import run_compliance_for_matches

router = APIRouter()


class ComplianceRunRequest(BaseModel):
    import_job_id: UUID | None = None


class ComplianceRunResponse(BaseModel):
    checks_created: int
    passed: int
    discrepancies_created: int


@router.post("/compliance/run", response_model=ComplianceRunResponse)
async def run_compliance(
    body: ComplianceRunRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> ComplianceRunResponse:
    await set_rls_organization(db, org_id)
    result = await run_compliance_for_matches(db, organization_id=org_id, import_job_id=body.import_job_id)
    await db.commit()
    return ComplianceRunResponse(
        checks_created=result.checks_created,
        passed=result.passed,
        discrepancies_created=result.discrepancies_created,
    )


class DiscrepancySummary(BaseModel):
    id: UUID
    billed_amount_minor: int
    allowed_amount_minor: int
    variance_minor: int
    currency_code: str
    reason_codes: list[str]
    review_status: str
    created_at: str


class DiscrepancyDetail(DiscrepancySummary):
    trace_summary: dict
    review_comment: str | None = None
    match_id: UUID | None = None
    shipment_id: UUID | None = None
    carrier_invoice_line_id: UUID | None = None


class DiscrepancyReviewPatch(BaseModel):
    review_status: DiscrepancyReviewStatus
    review_comment: str = Field(min_length=1)


@router.get("/discrepancies", response_model=list[DiscrepancySummary])
async def list_discrepancies(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> list[DiscrepancySummary]:
    await set_rls_organization(db, org_id)
    rows = (
        await db.scalars(
            select(Discrepancy)
            .where(Discrepancy.organization_id == org_id)
            .order_by(Discrepancy.created_at.desc())
        )
    ).all()
    return [
        DiscrepancySummary(
            id=row.id,
            billed_amount_minor=row.billed_amount_minor,
            allowed_amount_minor=row.allowed_amount_minor,
            variance_minor=row.variance_minor,
            currency_code=row.currency_code,
            reason_codes=list(row.reason_codes or []),
            review_status=row.review_status.value,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.get("/discrepancies/{discrepancy_id}", response_model=DiscrepancyDetail)
async def get_discrepancy(
    discrepancy_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DiscrepancyDetail:
    await set_rls_organization(db, org_id)
    row = await db.scalar(
        select(Discrepancy)
        .where(Discrepancy.id == discrepancy_id, Discrepancy.organization_id == org_id)
        .options(selectinload(Discrepancy.compliance_check))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Discrepancy not found")

    check = row.compliance_check
    match_id = check.shipment_invoice_match_id if check else None
    shipment_id = None
    invoice_line_id = None
    if check:
        from app.models import ShipmentInvoiceMatch

        match = await db.get(ShipmentInvoiceMatch, check.shipment_invoice_match_id)
        if match:
            shipment_id = match.shipment_id
            invoice_line_id = match.carrier_invoice_line_id

    return DiscrepancyDetail(
        id=row.id,
        billed_amount_minor=row.billed_amount_minor,
        allowed_amount_minor=row.allowed_amount_minor,
        variance_minor=row.variance_minor,
        currency_code=row.currency_code,
        reason_codes=list(row.reason_codes or []),
        review_status=row.review_status.value,
        created_at=row.created_at.isoformat(),
        trace_summary=dict(row.trace_summary_json or {}),
        review_comment=row.review_comment,
        match_id=match_id,
        shipment_id=shipment_id,
        carrier_invoice_line_id=invoice_line_id,
    )


@router.patch("/discrepancies/{discrepancy_id}", response_model=DiscrepancyDetail)
async def review_discrepancy(
    discrepancy_id: UUID,
    body: DiscrepancyReviewPatch,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> DiscrepancyDetail:
    await set_rls_organization(db, org_id)
    row = await db.scalar(
        select(Discrepancy)
        .where(Discrepancy.id == discrepancy_id, Discrepancy.organization_id == org_id)
        .options(selectinload(Discrepancy.compliance_check))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Discrepancy not found")

    previous = row.review_status.value
    row.review_status = body.review_status
    row.review_comment = body.review_comment.strip()
    row.reviewed_at = datetime.now(UTC)
    db.add(
        DiscrepancyEvent(
            organization_id=org_id,
            discrepancy_id=row.id,
            event_type="review_updated",
            payload_json={
                "previous_status": previous,
                "new_status": body.review_status.value,
                "review_comment": row.review_comment,
            },
        )
    )
    await db.commit()
    await db.refresh(row)

    check = row.compliance_check
    match_id = check.shipment_invoice_match_id if check else None
    shipment_id = None
    invoice_line_id = None
    if check:
        from app.models import ShipmentInvoiceMatch

        match = await db.get(ShipmentInvoiceMatch, check.shipment_invoice_match_id)
        if match:
            shipment_id = match.shipment_id
            invoice_line_id = match.carrier_invoice_line_id

    return DiscrepancyDetail(
        id=row.id,
        billed_amount_minor=row.billed_amount_minor,
        allowed_amount_minor=row.allowed_amount_minor,
        variance_minor=row.variance_minor,
        currency_code=row.currency_code,
        reason_codes=list(row.reason_codes or []),
        review_status=row.review_status.value,
        created_at=row.created_at.isoformat(),
        trace_summary=dict(row.trace_summary_json or {}),
        review_comment=row.review_comment,
        match_id=match_id,
        shipment_id=shipment_id,
        carrier_invoice_line_id=invoice_line_id,
    )
