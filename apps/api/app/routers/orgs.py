from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.models import Organization
from app.services.org_settings import (
    apply_platform_recovery_fee,
    apply_profile_patch,
    merge_client_settings,
    profile_from_org,
)
from app.tenancy import get_organization_id

router = APIRouter()


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    slug: str
    partner_id: str | None
    settings_json: dict = Field(default_factory=dict)


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    partner_id: str | None = None


class OrganizationClientPatch(BaseModel):
    autonomy_tier: str | None = None
    carrier_billing_emails: dict | None = None
    recovery_fee_bps: int | None = None


class RecoveryFeePatch(BaseModel):
    recovery_fee_bps: int


class ProfileContacts(BaseModel):
    primary_name: str | None = None
    primary_email: str | None = None
    billing_email: str | None = None
    disputes_email: str | None = None


class ProfilePerson(BaseModel):
    name: str = ""
    email: str = ""
    role: str = "viewer"


class OrganizationProfileOut(BaseModel):
    id: UUID
    name: str
    slug: str
    partner_id: str | None = None
    contacts: dict = Field(default_factory=dict)
    people: list[dict] = Field(default_factory=list)
    carriers: list[str] = Field(default_factory=list)
    tolerances: dict = Field(default_factory=dict)
    autonomy_tier: str
    carrier_billing_emails: dict = Field(default_factory=dict)
    recovery_fee_bps: int
    setup_complete: bool


class OrganizationProfilePatch(BaseModel):
    name: str | None = None
    contacts: ProfileContacts | None = None
    people: list[ProfilePerson] | None = None
    carriers: list[str] | None = None
    tolerances: dict | None = None
    autonomy_tier: str | None = None
    carrier_billing_emails: dict | None = None
    recovery_fee_bps: int | None = None


@router.post("/organizations", response_model=OrganizationOut)
async def create_organization(body: OrganizationCreate, db: AsyncSession = Depends(get_db)) -> OrganizationOut:
    """Dev bootstrap — creates org without auth."""
    existing = await db.scalar(select(Organization).where(Organization.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")
    org = Organization(name=body.name, slug=body.slug, partner_id=body.partner_id)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        partner_id=org.partner_id,
        settings_json=org.settings_json or {},
    )


@router.get("/organizations/current", response_model=OrganizationOut)
async def get_current_organization(db: AsyncSession = Depends(get_db)) -> OrganizationOut:
    org_id = get_organization_id()
    if org_id is None:
        raise HTTPException(status_code=400, detail="Missing organization context")
    await set_rls_organization(db, org_id)
    org = await db.scalar(select(Organization).where(Organization.id == org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        partner_id=org.partner_id,
        settings_json=org.settings_json or {},
    )


def _org_out(org: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        partner_id=org.partner_id,
        settings_json=org.settings_json or {},
    )


async def _require_current_org(db: AsyncSession) -> Organization:
    org_id = get_organization_id()
    if org_id is None:
        raise HTTPException(status_code=400, detail="Missing organization context")
    await set_rls_organization(db, org_id)
    org = await db.scalar(select(Organization).where(Organization.id == org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/organizations/current", response_model=OrganizationOut)
async def patch_current_organization(
    body: OrganizationClientPatch,
    db: AsyncSession = Depends(get_db),
) -> OrganizationOut:
    org = await _require_current_org(db)
    patch: dict = {}
    if body.autonomy_tier is not None:
        patch["autonomy_tier"] = body.autonomy_tier
    if body.carrier_billing_emails is not None:
        patch["carrier_billing_emails"] = body.carrier_billing_emails
    try:
        org.settings_json = merge_client_settings(org.settings_json or {}, patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(org)
    return _org_out(org)


def _profile_out(org: Organization) -> OrganizationProfileOut:
    return OrganizationProfileOut.model_validate(profile_from_org(org))


@router.get("/organizations/current/profile", response_model=OrganizationProfileOut)
async def get_current_profile(db: AsyncSession = Depends(get_db)) -> OrganizationProfileOut:
    org = await _require_current_org(db)
    return _profile_out(org)


@router.patch("/organizations/current/profile", response_model=OrganizationProfileOut)
async def patch_current_profile(
    body: OrganizationProfilePatch,
    db: AsyncSession = Depends(get_db),
) -> OrganizationProfileOut:
    org = await _require_current_org(db)
    payload = body.model_dump(exclude_none=True)
    payload.pop("recovery_fee_bps", None)
    try:
        apply_profile_patch(org, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(org)
    return _profile_out(org)


@router.patch("/organizations/current/recovery-fee", response_model=OrganizationOut)
async def patch_recovery_fee(
    body: RecoveryFeePatch,
    db: AsyncSession = Depends(get_db),
    x_platform_admin: str | None = Header(default=None, alias="X-Platform-Admin"),
) -> OrganizationOut:
    if x_platform_admin != "1":
        raise HTTPException(status_code=403, detail="Platform admin required")
    org = await _require_current_org(db)
    try:
        org.settings_json = apply_platform_recovery_fee(org.settings_json or {}, body.recovery_fee_bps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(org)
    return _org_out(org)
