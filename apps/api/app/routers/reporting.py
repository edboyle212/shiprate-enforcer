from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.routers.imports import require_org_id
from app.services.reporting import get_reporting_summary

router = APIRouter()


class ReportingSummaryOut(BaseModel):
    discrepancy_count: int
    total_overcharge_minor: int
    open_disputes: int
    recovered_total_minor: int
    fee_total_minor: int
    import_job_count: int = 0
    compliance_rate: float | None
    compliance_rate_note: str | None = None


@router.get("/reporting/summary", response_model=ReportingSummaryOut)
async def reporting_summary(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> ReportingSummaryOut:
    await set_rls_organization(db, org_id)
    summary = await get_reporting_summary(db, org_id)
    return ReportingSummaryOut(
        discrepancy_count=summary.discrepancy_count,
        total_overcharge_minor=summary.total_overcharge_minor,
        open_disputes=summary.open_disputes,
        recovered_total_minor=summary.recovered_total_minor,
        fee_total_minor=summary.fee_total_minor,
        import_job_count=summary.import_job_count,
        compliance_rate=summary.compliance_rate,
        compliance_rate_note=summary.compliance_rate_note,
    )
