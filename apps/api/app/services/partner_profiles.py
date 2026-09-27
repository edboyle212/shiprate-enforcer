from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WmsPartner


async def get_partner_profile(db: AsyncSession, partner_id: str) -> dict:
    row = await db.scalar(select(WmsPartner).where(WmsPartner.partner_id == partner_id))
    if not row:
        return {}
    return {
        "partner_id": row.partner_id,
        "display_name": row.display_name,
        **(row.profile_json or {}),
        "branding": row.branding_json or {},
    }


async def upsert_partner_profile(
    db: AsyncSession,
    partner_id: str,
    profile: dict,
    branding: dict | None = None,
) -> dict:
    row = await db.scalar(select(WmsPartner).where(WmsPartner.partner_id == partner_id))
    display_name = profile.pop("partner_name", None) or profile.pop("display_name", None)
    branding_payload = branding or {}
    for key in ("branding_mode", "logo_url", "primary_color", "support_email", "display_name"):
        if key in profile:
            branding_payload[key] = profile.pop(key)

    if row is None:
        row = WmsPartner(
            partner_id=partner_id,
            display_name=display_name,
            profile_json=profile,
            branding_json=branding_payload,
        )
        db.add(row)
    else:
        merged = dict(row.profile_json or {})
        merged.update(profile)
        row.profile_json = merged
        if display_name:
            row.display_name = display_name
        bmerged = dict(row.branding_json or {})
        bmerged.update(branding_payload)
        row.branding_json = bmerged

    await db.commit()
    await db.refresh(row)
    return {
        "partner_id": row.partner_id,
        "display_name": row.display_name,
        **(row.profile_json or {}),
        "branding": row.branding_json or {},
    }
