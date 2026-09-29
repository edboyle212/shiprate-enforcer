"""Carrier contact resolution."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import CarrierContact
from app.services.carrier_contacts import resolve_carrier_email

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_resolve_carrier_email(db_session):
    code = "UPS"
    existing = await db_session.scalar(
        select(CarrierContact).where(
            CarrierContact.carrier_code == code,
            CarrierContact.channel == "email",
        )
    )
    if existing is None:
        db_session.add(
            CarrierContact(
                id=uuid.uuid4(),
                carrier_code=code,
                channel="email",
                address="billing@ups.test",
            )
        )
        await db_session.flush()

    assert await resolve_carrier_email(db_session, "ups") == "billing@ups.test"
    assert await resolve_carrier_email(db_session, "ZZZUNKNOWN") is None
    assert await resolve_carrier_email(db_session, None) is None
