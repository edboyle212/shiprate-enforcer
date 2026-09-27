from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.etl_file_drop import poll_etl_drop
from app.tenancy import get_organization_id

router = APIRouter()


class PollDropRequest(BaseModel):
    partner_id: str


class PollDropResponse(BaseModel):
    partner_id: str
    ingested: list[str]
    skipped: list[str]


def require_org_id() -> UUID:
    from fastapi import HTTPException

    org_id = get_organization_id()
    if org_id is None:
        raise HTTPException(status_code=400, detail="Missing organization context (X-Organization-Id)")
    return org_id


@router.post("/etl/poll-drop", response_model=PollDropResponse)
async def poll_drop(
    body: PollDropRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> PollDropResponse:
    result = await poll_etl_drop(db, partner_id=body.partner_id, organization_id=org_id)
    return PollDropResponse(
        partner_id=result["partner_id"],
        ingested=result["ingested"],
        skipped=result["skipped"],
    )
