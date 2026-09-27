from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.models import RateCardVersion, RateCardVersionStatus, RatingExplanation, RatingRun, RatingRunStatus
from app.rating.engine import rate as rate_request
from app.routers.imports import require_org_id

router = APIRouter()


class RatingRunRequest(BaseModel):
    rate_card_version_id: UUID
    shipments: list[dict] = Field(default_factory=list)


class RatingRunResponse(BaseModel):
    id: UUID
    status: str
    allowed_total_minor: int
    currency_code: str
    explanations: list[dict]


@router.post("/rating-runs", response_model=RatingRunResponse)
async def create_rating_run(
    body: RatingRunRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> RatingRunResponse:
    await set_rls_organization(db, org_id)

    rc = await db.scalar(
        select(RateCardVersion).where(
            RateCardVersion.id == body.rate_card_version_id,
            RateCardVersion.organization_id == org_id,
        )
    )
    if not rc:
        raise HTTPException(status_code=404, detail="Rate card not found")
    if rc.status != RateCardVersionStatus.approved:
        raise HTTPException(status_code=400, detail="Rate card must be approved before rating")

    run = RatingRun(
        organization_id=org_id,
        rate_card_version_id=rc.id,
        status=RatingRunStatus.pending,
        input_snapshot_json={"shipments": body.shipments},
    )
    db.add(run)
    await db.flush()

    total_minor = 0
    currency = "USD"
    explanations_out: list[dict] = []

    for shipment in body.shipments:
        request_payload = {
            **shipment,
            "rate_card_version_id": str(rc.id),
            "contract_version_id": str(rc.id),
            "currency_code": shipment.get("currency_code", "USD"),
            "rate_card_snapshot": rc.rules_json,
        }
        result = rate_request(request_payload)
        total_minor += result["allowed_total_minor"]
        currency = result["currency_code"]
        expl = RatingExplanation(
            organization_id=org_id,
            rating_run_id=run.id,
            trace_json=result["trace"],
            allowed_amount_minor=result["allowed_total_minor"],
            currency_code=result["currency_code"],
        )
        db.add(expl)
        explanations_out.append(
            {
                "allowed_amount_minor": result["allowed_total_minor"],
                "currency_code": result["currency_code"],
                "trace": result["trace"],
            }
        )

    run.status = RatingRunStatus.completed
    run.result_json = {"allowed_total_minor": total_minor, "currency_code": currency}
    await db.commit()
    await db.refresh(run)

    return RatingRunResponse(
        id=run.id,
        status=run.status.value,
        allowed_total_minor=total_minor,
        currency_code=currency,
        explanations=explanations_out,
    )
