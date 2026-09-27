from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.models import Organization
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
