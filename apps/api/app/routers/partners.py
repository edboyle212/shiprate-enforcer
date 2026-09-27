from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.partner_profiles import get_partner_profile, upsert_partner_profile

router = APIRouter()


class PartnerProfilePayload(BaseModel):
    partner_name: str | None = None
    branding_mode: str | None = None
    display_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    support_email: str | None = None
    export_methods: list[str] = Field(default_factory=list)
    export_fields: dict | None = None
    carriers: list[str] = Field(default_factory=list)
    embed_mode: str | None = None
    ingest_mode: str | None = None
    is_3pl: bool | None = None
    notes: str | None = None
    client_invite_base_url: str | None = None


@router.get("/partners/{partner_id}/profile")
async def read_partner_profile(partner_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return await get_partner_profile(db, partner_id)


@router.put("/partners/{partner_id}/profile")
async def write_partner_profile(
    partner_id: str,
    body: PartnerProfilePayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = body.model_dump(exclude_none=True)
    branding_keys = ("branding_mode", "logo_url", "primary_color", "support_email", "display_name")
    branding = {k: payload.pop(k) for k in branding_keys if k in payload}
    return await upsert_partner_profile(db, partner_id, payload, branding)


@router.get("/partners/{partner_id}/public-branding")
async def public_branding(partner_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    profile = await get_partner_profile(db, partner_id)
    branding = profile.get("branding") or {}
    return {
        "partner_id": partner_id,
        "display_name": profile.get("display_name") or partner_id,
        "branding_mode": branding.get("branding_mode"),
        "logo_url": branding.get("logo_url"),
        "primary_color": branding.get("primary_color") or "#059669",
    }
