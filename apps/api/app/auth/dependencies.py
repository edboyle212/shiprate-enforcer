from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException

from app.auth.context import get_principal
from app.auth.principal import Principal


def require_principal() -> Principal:
    principal = get_principal()
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_org_id(principal: Principal = Depends(require_principal)) -> UUID:
    if principal.organization_id is None:
        raise HTTPException(status_code=400, detail="Organization context required")
    if principal.membership_role is None and not principal.is_platform_admin:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return principal.organization_id


def require_platform_admin(principal: Principal = Depends(require_principal)) -> Principal:
    if not principal.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin required")
    return principal


def require_partner_access(
    partner_id: str,
    principal: Principal = Depends(require_principal),
) -> str:
    if not principal.has_partner_access(partner_id):
        raise HTTPException(status_code=403, detail="Partner access required")
    return partner_id
