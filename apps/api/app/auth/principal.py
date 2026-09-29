from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    external_auth_id: str
    organization_id: UUID | None = None
    membership_role: str | None = None
    is_platform_admin: bool = False
    partner_ids: frozenset[str] = field(default_factory=frozenset)

    def has_partner_access(self, partner_id: str) -> bool:
        if self.is_platform_admin:
            return True
        return partner_id in self.partner_ids
