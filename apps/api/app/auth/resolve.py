"""Resolve HTTP credentials to a Principal."""

from __future__ import annotations

import uuid
from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.clerk import verify_clerk_token
from app.auth.principal import Principal
from app.config import allow_dev_tenant_header, allow_test_bearer, settings, try_demo_public_mode
from app.models import OrganizationMembership, PartnerMembership, PlatformAdmin, User


async def principal_from_bearer(session: AsyncSession, authorization: str | None) -> Principal | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None

    if allow_test_bearer() and token.startswith("shiprate-test:"):
        return await _principal_from_test_token(session, token)

    if settings.clerk_jwt_issuer or settings.clerk_secret_key:
        try:
            claims = verify_clerk_token(token)
        except JWTError:
            return None
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            return None
        org_claim = claims.get("org_id") or claims.get("o", {}).get("id") if isinstance(claims.get("o"), dict) else None
        org_id: UUID | None = None
        if isinstance(org_claim, str):
            try:
                org_id = UUID(org_claim)
            except ValueError:
                org_id = None
        return await _principal_for_external_user(session, sub, org_id)

    return None


async def _principal_from_test_token(session: AsyncSession, token: str) -> Principal | None:
    # shiprate-test:<external_auth_id>:<organization_uuid>
    parts = token.split(":", 2)
    if len(parts) != 3 or parts[0] != "shiprate-test":
        return None
    external_id, org_raw = parts[1], parts[2]
    try:
        org_id = UUID(org_raw)
    except ValueError:
        return None
    if settings.env == "test" or (settings.env == "staging" and try_demo_public_mode()):
        return Principal(
            user_id=uuid.uuid4(),
            external_auth_id=external_id,
            organization_id=org_id,
            membership_role="owner",
            is_platform_admin=external_id in ("test-platform-admin",) or external_id.endswith("-admin"),
            partner_ids=frozenset({"northstar"}),
        )
    return await _principal_for_external_user(session, external_id, org_id)


async def _principal_for_external_user(
    session: AsyncSession,
    external_auth_id: str,
    organization_id: UUID | None,
) -> Principal | None:
    user = await session.scalar(select(User).where(User.external_auth_id == external_auth_id))
    if user is None:
        return None

    is_platform = await session.scalar(select(PlatformAdmin).where(PlatformAdmin.user_id == user.id))
    partner_rows = await session.scalars(select(PartnerMembership.partner_id).where(PartnerMembership.user_id == user.id))
    partner_ids = frozenset(partner_rows.all())

    membership_role: str | None = None
    if organization_id is not None:
        membership = await session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == organization_id,
            )
        )
        if membership is None and not is_platform:
            return None
        if membership is not None:
            membership_role = membership.role.value

    return Principal(
        user_id=user.id,
        external_auth_id=external_auth_id,
        organization_id=organization_id,
        membership_role=membership_role,
        is_platform_admin=is_platform is not None,
        partner_ids=partner_ids,
    )


async def principal_from_dev_header(
    session: AsyncSession,
    org_header: str | None,
    clerk_org_header: str | None,
) -> Principal | None:
    """Legacy dev path — only when explicitly allowed."""
    if not allow_dev_tenant_header():
        return None
    org_raw = org_header
    if org_raw is None and clerk_org_header and settings.clerk_secret_key:
        org_raw = clerk_org_header
    if not org_raw:
        return None
    try:
        org_id = UUID(org_raw)
    except ValueError:
        return None
    if settings.env == "test":
        return Principal(
            user_id=uuid.uuid4(),
            external_auth_id=settings.dev_bootstrap_user_external_id,
            organization_id=org_id,
            membership_role="owner",
        )
    dev_user = await session.scalar(select(User).where(User.external_auth_id == settings.dev_bootstrap_user_external_id))
    if dev_user is None:
        return None
    return await _principal_for_external_user(session, dev_user.external_auth_id, org_id)
