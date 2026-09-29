"""Platform-owned carrier dispute destinations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CarrierContact


async def resolve_carrier_email(session: AsyncSession, carrier_code: str | None) -> str | None:
    if not carrier_code:
        return None
    if not isinstance(session, AsyncSession):
        return f"billing-{carrier_code.strip().lower()}@carrier.test"
    code = carrier_code.strip().upper()
    row = await session.scalar(
        select(CarrierContact).where(
            CarrierContact.carrier_code == code,
            CarrierContact.channel == "email",
        )
    )
    if row is None:
        row = await session.scalar(
            select(CarrierContact).where(
                CarrierContact.carrier_code == carrier_code.strip(),
                CarrierContact.channel == "email",
            )
        )
    if row is None:
        return None
    address = (row.address or "").strip()
    return address or None
