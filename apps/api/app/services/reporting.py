"""Reporting KPIs for dashboard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ComplianceCheck, Discrepancy, DisputeCase, DisputeCaseStatus, ImportJob
from app.services.negotiation import OPEN_DISPUTE_STATUSES


@dataclass
class ReportingSummary:
    discrepancy_count: int
    total_overcharge_minor: int
    open_disputes: int
    recovered_total_minor: int
    fee_total_minor: int
    import_job_count: int
    compliance_rate: float | None
    compliance_rate_note: str | None


async def get_reporting_summary(session: AsyncSession, organization_id: uuid.UUID) -> ReportingSummary:
    disc_count = await session.scalar(
        select(func.count()).select_from(Discrepancy).where(Discrepancy.organization_id == organization_id)
    )
    total_overcharge = await session.scalar(
        select(func.coalesce(func.sum(Discrepancy.variance_minor), 0)).where(
            Discrepancy.organization_id == organization_id,
            Discrepancy.variance_minor > 0,
        )
    )
    open_disputes = await session.scalar(
        select(func.count())
        .select_from(DisputeCase)
        .where(DisputeCase.organization_id == organization_id, DisputeCase.status.in_(OPEN_DISPUTE_STATUSES))
    )
    recovered_total = await session.scalar(
        select(func.coalesce(func.sum(DisputeCase.recovered_amount_minor), 0)).where(
            DisputeCase.organization_id == organization_id,
            DisputeCase.status == DisputeCaseStatus.credited,
        )
    )
    fee_total = await session.scalar(
        select(func.coalesce(func.sum(DisputeCase.fee_amount_minor), 0)).where(
            DisputeCase.organization_id == organization_id,
            DisputeCase.status == DisputeCaseStatus.credited,
        )
    )
    import_job_count = await session.scalar(
        select(func.count()).select_from(ImportJob).where(ImportJob.organization_id == organization_id)
    )

    check_total = await session.scalar(
        select(func.count()).select_from(ComplianceCheck).where(ComplianceCheck.organization_id == organization_id)
    )
    passed = await session.scalar(
        select(func.count())
        .select_from(ComplianceCheck)
        .where(ComplianceCheck.organization_id == organization_id, ComplianceCheck.within_tolerance.is_(True))
    )

    compliance_rate: float | None = None
    note: str | None = None
    if check_total and check_total > 0:
        compliance_rate = round(float(passed or 0) / float(check_total), 4)
    else:
        note = "No compliance checks yet"

    return ReportingSummary(
        discrepancy_count=int(disc_count or 0),
        total_overcharge_minor=int(total_overcharge or 0),
        open_disputes=int(open_disputes or 0),
        recovered_total_minor=int(recovered_total or 0),
        fee_total_minor=int(fee_total or 0),
        import_job_count=int(import_job_count or 0),
        compliance_rate=compliance_rate,
        compliance_rate_note=note,
    )
