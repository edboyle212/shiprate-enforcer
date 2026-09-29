from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_org_id
from app.db import get_db, set_rls_organization
from app.models import Organization
from app.services.etl_file_drop import poll_etl_drop

router = APIRouter()


class PollDropResponse(BaseModel):
    partner_id: str
    ingested: list[str]
    skipped: list[str]


@router.post("/etl/poll-drop", response_model=PollDropResponse)
async def poll_drop(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> PollDropResponse:
    await set_rls_organization(db, org_id)
    org = await db.scalar(select(Organization).where(Organization.id == org_id))
    if not org or not org.partner_id:
        raise HTTPException(status_code=400, detail="Organization has no partner_id")
    result = await poll_etl_drop(db, partner_id=org.partner_id, organization_id=org_id)
    return PollDropResponse(
        partner_id=result["partner_id"],
        ingested=result["ingested"],
        skipped=result["skipped"],
    )
