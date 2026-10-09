import csv
import io
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CarrierInvoiceLine,
    EtlProcessedObject,
    ImportJob,
    ImportJobStatus,
    ImportRow,
    Shipment,
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


def _parse_amount_minor(raw: str | None) -> int:
    if not raw:
        return 0
    value = float(raw.replace(",", "").strip())
    return round(value * 100)


async def process_etl_pending_import_jobs(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> dict:
    """Map CSV rows for pending jobs created by ``poll_etl_drop`` (same columns as manual import)."""
    from app.db import set_rls_organization

    await set_rls_organization(db, organization_id)

    jobs = list(
        (
            await db.scalars(
                select(ImportJob).where(
                    ImportJob.organization_id == organization_id,
                    ImportJob.status == ImportJobStatus.pending,
                    ImportJob.idempotency_key.startswith("etl:"),
                )
            )
        ).all()
    )

    shipments_created = 0
    invoice_lines_created = 0
    jobs_completed = 0

    for job in jobs:
        source = await db.scalar(
            select(SourceFile).where(
                SourceFile.id == job.source_file_id,
                SourceFile.organization_id == organization_id,
            )
        )
        if not source:
            continue

        data = storage_service.read_object(source.storage_key)
        text = data.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        if source.kind == SourceFileKind.shipment_export:
            for idx, row in enumerate(reader, start=1):
                db.add(
                    ImportRow(
                        organization_id=organization_id,
                        import_job_id=job.id,
                        row_number=idx,
                        raw_json=dict(row),
                    )
                )
                weight_raw = row.get("weight_oz")
                weight_oz = int(float(weight_raw)) if weight_raw else None
                db.add(
                    Shipment(
                        organization_id=organization_id,
                        import_job_id=job.id,
                        tracking_number=row.get("tracking_number") or None,
                        carrier_code=row.get("carrier"),
                        service_code=row.get("service"),
                        dest_postal=row.get("dest_postal"),
                        weight_oz=weight_oz,
                    )
                )
                shipments_created += 1
        elif source.kind == SourceFileKind.carrier_invoice:
            for idx, row in enumerate(reader, start=1):
                db.add(
                    ImportRow(
                        organization_id=organization_id,
                        import_job_id=job.id,
                        row_number=idx,
                        raw_json=dict(row),
                    )
                )
                db.add(
                    CarrierInvoiceLine(
                        organization_id=organization_id,
                        import_job_id=job.id,
                        tracking_number=row.get("tracking_number") or None,
                        charge_code=row.get("charge_code"),
                        description=row.get("description"),
                        billed_amount_minor=_parse_amount_minor(row.get("billed_amount")),
                        currency_code="USD",
                    )
                )
                invoice_lines_created += 1
        else:
            continue

        job.status = ImportJobStatus.completed
        jobs_completed += 1

    await db.commit()
    return {
        "jobs_completed": jobs_completed,
        "shipments_created": shipments_created,
        "invoice_lines_created": invoice_lines_created,
    }
