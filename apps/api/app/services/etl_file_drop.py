from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EtlProcessedObject,
    ImportJob,
    ImportJobStatus,
    SourceFile,
    SourceFileKind,
)
from app.services.storage import storage_service

FOLDER_KIND = {
    "shipments": SourceFileKind.shipment_export,
    "invoices": SourceFileKind.carrier_invoice,
    "rate_cards": SourceFileKind.rate_card,
}


async def poll_etl_drop(
    db: AsyncSession,
    *,
    partner_id: str,
    organization_id: UUID,
) -> dict:
    """FileDropAdapter: ingest new objects from partner ETL prefix."""
    from app.db import set_rls_organization

    await set_rls_organization(db, organization_id)

    ingested: list[str] = []
    skipped: list[str] = []

    for subfolder, kind in FOLDER_KIND.items():
        keys = storage_service.list_etl_objects(partner_id, str(organization_id), subfolder)
        for key in keys:
            seen = await db.scalar(
                select(EtlProcessedObject).where(
                    EtlProcessedObject.organization_id == organization_id,
                    EtlProcessedObject.storage_key == key,
                )
            )
            if seen:
                skipped.append(key)
                continue

            data = storage_service.read_object(key)
            filename = key.split("/")[-1]
            immutable_key, digest = storage_service.put_immutable(str(organization_id), filename, data)

            existing_file = await db.scalar(
                select(SourceFile).where(
                    SourceFile.organization_id == organization_id,
                    SourceFile.sha256_hex == digest,
                )
            )
            if existing_file:
                source = existing_file
            else:
                source = SourceFile(
                    organization_id=organization_id,
                    kind=kind,
                    original_filename=filename,
                    content_type=None,
                    byte_size=len(data),
                    sha256_hex=digest,
                    storage_key=immutable_key,
                    storage_backend=storage_service.backend_name,
                )
                db.add(source)
                await db.flush()

            idempotency_key = f"etl:{key}"
            existing_job = await db.scalar(
                select(ImportJob).where(
                    ImportJob.organization_id == organization_id,
                    ImportJob.idempotency_key == idempotency_key,
                )
            )
            if not existing_job:
                job = ImportJob(
                    organization_id=organization_id,
                    source_file_id=source.id,
                    idempotency_key=idempotency_key,
                    sha256_hex=digest,
                    status=ImportJobStatus.pending,
                )
                db.add(job)

            db.add(
                EtlProcessedObject(
                    organization_id=organization_id,
                    storage_key=key,
                    sha256_hex=digest,
                )
            )
            ingested.append(key)

    await db.commit()
    return {"ingested": ingested, "skipped": skipped, "partner_id": partner_id}
