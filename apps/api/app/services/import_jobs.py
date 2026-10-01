"""Import job service (sync) for idempotency integration tests."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import (
    ImportJob,
    ImportJobStatus,
    Organization,
    SourceFile,
    SourceFileKind,
)


def _ensure_organization(session: Session, organization_id: uuid.UUID) -> None:
    session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": str(organization_id)},
    )
    if session.get(Organization, organization_id) is None:
        slug = f"org-{organization_id.hex}"
        session.add(Organization(id=organization_id, name=slug, slug=slug))
        session.flush()

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def _ensure_source_file(session: Session, organization_id: uuid.UUID, sha256: str) -> SourceFile:
    existing = session.scalar(
        select(SourceFile).where(
            SourceFile.organization_id == organization_id,
            SourceFile.sha256_hex == sha256,
        )
    )
    if existing:
        return existing
    sf = SourceFile(
        organization_id=organization_id,
        kind=SourceFileKind.shipment_export,
        original_filename=f"{sha256}.csv",
        byte_size=0,
        sha256_hex=sha256,
        storage_key=f"test/{sha256}",
        storage_backend="test",
    )
    session.add(sf)
    session.flush()
    return sf


def create_import_job(
    *,
    organization_id: uuid.UUID,
    idempotency_key: str,
    source_file_sha256: str,
    kind: str,
    **_: Any,
) -> ImportJob:
    with SessionLocal() as session, session.begin():
        _ensure_organization(session, organization_id)
        existing = session.scalar(
            select(ImportJob).where(
                ImportJob.organization_id == organization_id,
                ImportJob.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing

        source = _ensure_source_file(session, organization_id, source_file_sha256)
        job = ImportJob(
            organization_id=organization_id,
            source_file_id=source.id,
            idempotency_key=idempotency_key,
            sha256_hex=source_file_sha256,
            status=ImportJobStatus.pending,
        )
        session.add(job)
        session.flush()
        session.refresh(job)
        return job


def count_import_jobs(*, organization_id: uuid.UUID, idempotency_key: str) -> int:
    with SessionLocal() as session:
        session.execute(
            text("SELECT set_config('app.organization_id', :org_id, true)"),
            {"org_id": str(organization_id)},
        )
        count = session.scalar(
            select(func.count())
            .select_from(ImportJob)
            .where(
                ImportJob.organization_id == organization_id,
                ImportJob.idempotency_key == idempotency_key,
            )
        )
        return int(count or 0)
