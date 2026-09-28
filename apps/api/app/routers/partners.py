import re
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.models import Organization
from app.services.org_settings import profile_from_org
from app.services.partner_profiles import get_partner_profile, upsert_partner_profile
from app.services.reporting import get_reporting_summary

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


class PartnerAccountCreate(BaseModel):
    name: str


class PartnerAccountListItem(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime | None = None
    setup_complete: bool


def _slug_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "warehouse"
    return slug


def _setup_complete(org: Organization) -> bool:
    onboarding = (org.settings_json or {}).get("client_onboarding") or {}
    return bool(onboarding.get("completed_at"))


@router.get("/partners/{partner_id}/accounts", response_model=list[PartnerAccountListItem])
async def list_partner_accounts(partner_id: str, db: AsyncSession = Depends(get_db)) -> list[PartnerAccountListItem]:
    result = await db.scalars(
        select(Organization).where(Organization.partner_id == partner_id).order_by(Organization.created_at.desc())
    )
    rows = result.all()
    return [
        PartnerAccountListItem(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at,
            setup_complete=_setup_complete(org),
        )
        for org in rows
    ]


@router.post("/partners/{partner_id}/accounts", response_model=PartnerAccountListItem)
async def create_partner_account(
    partner_id: str,
    body: PartnerAccountCreate,
    db: AsyncSession = Depends(get_db),
) -> PartnerAccountListItem:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    slug = _slug_from_name(name)
    existing = await db.scalar(select(Organization).where(Organization.slug == slug))
    if existing:
        slug = f"{slug[:39]}-{uuid4().hex[:8]}"
    org = Organization(name=name, slug=slug, partner_id=partner_id)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return PartnerAccountListItem(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_at=org.created_at,
        setup_complete=False,
    )


@router.get("/partners/{partner_id}/accounts/{org_id}")
async def get_partner_account(
    partner_id: str,
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await db.scalar(select(Organization).where(Organization.id == org_id))
    if not org or org.partner_id != partner_id:
        raise HTTPException(status_code=404, detail="Account not found")
    await set_rls_organization(db, org.id)
    summary = await get_reporting_summary(db, org.id)
    return {
        "profile": profile_from_org(org),
        "summary": {
            "discrepancy_count": summary.discrepancy_count,
            "total_overcharge_minor": summary.total_overcharge_minor,
            "open_disputes": summary.open_disputes,
            "recovered_total_minor": summary.recovered_total_minor,
            "fee_total_minor": summary.fee_total_minor,
            "compliance_rate": summary.compliance_rate,
            "compliance_rate_note": summary.compliance_rate_note,
            "import_job_count": summary.import_job_count,
        },
    }
