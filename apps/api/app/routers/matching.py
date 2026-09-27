from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.routers.imports import require_org_id
from app.services.compliance import run_compliance_for_matches
from app.services.matching import create_manual_match, run_automatic_matching

router = APIRouter()


class MatchingRunRequest(BaseModel):
    import_job_id: UUID | None = None
    run_compliance: bool = True


class MatchingRunResponse(BaseModel):
    exact_matches: int
    normalized_matches: int
    skipped_already_matched: int
    compliance_checks_created: int | None = None
    discrepancies_created: int | None = None


@router.post("/matching/run", response_model=MatchingRunResponse)
async def run_matching(
    body: MatchingRunRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> MatchingRunResponse:
    await set_rls_organization(db, org_id)
    result = await run_automatic_matching(db, organization_id=org_id, import_job_id=body.import_job_id)
    compliance_checks_created = None
    discrepancies_created = None
    if body.run_compliance:
        comp = await run_compliance_for_matches(
            db, organization_id=org_id, import_job_id=body.import_job_id
        )
        compliance_checks_created = comp.checks_created
        discrepancies_created = comp.discrepancies_created
    await db.commit()
    return MatchingRunResponse(
        exact_matches=result.exact_matches,
        normalized_matches=result.normalized_matches,
        skipped_already_matched=result.skipped_already_matched,
        compliance_checks_created=compliance_checks_created,
        discrepancies_created=discrepancies_created,
    )


class ManualMatchRequest(BaseModel):
    shipment_id: UUID
    carrier_invoice_line_id: UUID


class ManualMatchResponse(BaseModel):
    id: UUID
    match_type: str


@router.post("/matching/manual-link", response_model=ManualMatchResponse)
async def manual_match_link(
    body: ManualMatchRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> ManualMatchResponse:
    await set_rls_organization(db, org_id)
    try:
        match = await create_manual_match(
            db,
            organization_id=org_id,
            shipment_id=body.shipment_id,
            carrier_invoice_line_id=body.carrier_invoice_line_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return ManualMatchResponse(id=match.id, match_type=match.match_type.value)
