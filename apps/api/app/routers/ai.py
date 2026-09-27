from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.routers.imports import require_org_id
from app.services.ai_mapping import map_columns

router = APIRouter()


class MapColumnsRequest(BaseModel):
    headers: list[str] = Field(min_length=1)
    kind: str = "shipment_export"


class MapColumnsResponse(BaseModel):
    mapping: dict[str, str]
    used_ai: bool
    provider: str | None = None
    request_id: UUID | None = None


@router.post("/ai/map-columns", response_model=MapColumnsResponse)
async def ai_map_columns(
    body: MapColumnsRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> MapColumnsResponse:
    await set_rls_organization(db, org_id)
    result = await map_columns(
        db,
        organization_id=org_id,
        headers=body.headers,
        kind=body.kind,
    )
    await db.commit()
    return MapColumnsResponse(
        mapping=result.mapping,
        used_ai=result.used_ai,
        provider=result.provider,
        request_id=result.request_id,
    )
