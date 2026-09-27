import csv
import io
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_rls_organization
from app.models import (
    ImportJob,
    ImportJobStatus,
    ImportRow,
    RateCardVersion,
    RateCardVersionStatus,
    Shipment,
    SourceFile,
    SourceFileKind,
)
from app.services.storage import sha256_hex, storage_service
from app.tenancy import get_organization_id

router = APIRouter()


def require_org_id() -> UUID:
    org_id = get_organization_id()
    if org_id is None:
        raise HTTPException(status_code=400, detail="Missing organization context (X-Organization-Id)")
    return org_id


class SourceFileOut(BaseModel):
    id: UUID
    kind: str
    original_filename: str
    sha256_hex: str
    storage_backend: str
    byte_size: int


class ImportJobOut(BaseModel):
    id: UUID
    source_file_id: UUID
    status: str
    sha256_hex: str
    idempotency_key: str


@router.post("/source-files", response_model=SourceFileOut)
async def upload_source_file(
    kind: SourceFileKind,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> SourceFileOut:
    await set_rls_organization(db, org_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    key, digest = storage_service.put_immutable(str(org_id), file.filename or "upload.bin", data)

    existing = await db.scalar(
        select(SourceFile).where(SourceFile.organization_id == org_id, SourceFile.sha256_hex == digest)
    )
    if existing:
        return SourceFileOut(
            id=existing.id,
            kind=existing.kind.value,
            original_filename=existing.original_filename,
            sha256_hex=existing.sha256_hex,
            storage_backend=existing.storage_backend,
            byte_size=existing.byte_size,
        )

    record = SourceFile(
        organization_id=org_id,
        kind=kind,
        original_filename=file.filename or "upload.bin",
        content_type=file.content_type,
        byte_size=len(data),
        sha256_hex=digest,
        storage_key=key,
        storage_backend=storage_service.backend_name,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return SourceFileOut(
        id=record.id,
        kind=record.kind.value,
        original_filename=record.original_filename,
        sha256_hex=record.sha256_hex,
        storage_backend=record.storage_backend,
        byte_size=record.byte_size,
    )


@router.post("/import-jobs", response_model=ImportJobOut)
async def create_import_job(
    source_file_id: UUID,
    idempotency_key: str,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> ImportJobOut:
    await set_rls_organization(db, org_id)

    existing = await db.scalar(
        select(ImportJob).where(
            ImportJob.organization_id == org_id,
            ImportJob.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return ImportJobOut(
            id=existing.id,
            source_file_id=existing.source_file_id,
            status=existing.status.value,
            sha256_hex=existing.sha256_hex,
            idempotency_key=existing.idempotency_key,
        )

    source = await db.scalar(
        select(SourceFile).where(SourceFile.id == source_file_id, SourceFile.organization_id == org_id)
    )
    if not source:
        raise HTTPException(status_code=404, detail="Source file not found")

    job = ImportJob(
        organization_id=org_id,
        source_file_id=source.id,
        idempotency_key=idempotency_key,
        sha256_hex=source.sha256_hex,
        status=ImportJobStatus.pending,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return ImportJobOut(
        id=job.id,
        source_file_id=job.source_file_id,
        status=job.status.value,
        sha256_hex=job.sha256_hex,
        idempotency_key=job.idempotency_key,
    )


class CsvColumnMapping(BaseModel):
    tracking_number: str = "tracking_number"
    carrier_code: str = "carrier"
    service_code: str = "service"
    dest_postal: str = "dest_postal"
    weight_oz: str = "weight_oz"


class MapCsvRequest(BaseModel):
    import_job_id: UUID
    mapping: CsvColumnMapping = Field(default_factory=CsvColumnMapping)
    csv_text: str


class MapCsvResponse(BaseModel):
    import_job_id: UUID
    rows_imported: int
    shipments_created: int


@router.post("/imports/map-csv", response_model=MapCsvResponse)
async def map_csv_shipments(
    body: MapCsvRequest,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> MapCsvResponse:
    await set_rls_organization(db, org_id)

    job = await db.scalar(
        select(ImportJob).where(ImportJob.id == body.import_job_id, ImportJob.organization_id == org_id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    reader = csv.DictReader(io.StringIO(body.csv_text))
    rows_imported = 0
    shipments_created = 0
    m = body.mapping

    for idx, row in enumerate(reader, start=1):
        rows_imported += 1
        db.add(
            ImportRow(
                organization_id=org_id,
                import_job_id=job.id,
                row_number=idx,
                raw_json=dict(row),
            )
        )
        tracking = row.get(m.tracking_number) or None
        weight_raw = row.get(m.weight_oz)
        weight_oz = int(float(weight_raw)) if weight_raw else None
        shipment = Shipment(
            organization_id=org_id,
            import_job_id=job.id,
            tracking_number=tracking,
            carrier_code=row.get(m.carrier_code),
            service_code=row.get(m.service_code),
            dest_postal=row.get(m.dest_postal),
            weight_oz=weight_oz,
        )
        db.add(shipment)
        shipments_created += 1

    job.status = ImportJobStatus.completed
    await db.commit()

    return MapCsvResponse(
        import_job_id=job.id,
        rows_imported=rows_imported,
        shipments_created=shipments_created,
    )


class RateCardCreate(BaseModel):
    carrier_code: str
    version_label: str
    rules_json: dict = Field(default_factory=dict)


class RateCardOut(BaseModel):
    id: UUID
    carrier_code: str
    version_label: str
    status: str
    rules_json: dict


@router.post("/rate-cards", response_model=RateCardOut)
async def create_rate_card(
    body: RateCardCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> RateCardOut:
    await set_rls_organization(db, org_id)
    rc = RateCardVersion(
        organization_id=org_id,
        carrier_code=body.carrier_code,
        version_label=body.version_label,
        rules_json=body.rules_json,
        status=RateCardVersionStatus.draft,
    )
    db.add(rc)
    await db.commit()
    await db.refresh(rc)
    return RateCardOut(
        id=rc.id,
        carrier_code=rc.carrier_code,
        version_label=rc.version_label,
        status=rc.status.value,
        rules_json=rc.rules_json,
    )


@router.post("/rate-cards/{rate_card_id}/approve", response_model=RateCardOut)
async def approve_rate_card(
    rate_card_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> RateCardOut:
    await set_rls_organization(db, org_id)
    rc = await db.scalar(
        select(RateCardVersion).where(
            RateCardVersion.id == rate_card_id,
            RateCardVersion.organization_id == org_id,
        )
    )
    if not rc:
        raise HTTPException(status_code=404, detail="Rate card not found")
    if rc.status == RateCardVersionStatus.approved:
        return RateCardOut(
            id=rc.id,
            carrier_code=rc.carrier_code,
            version_label=rc.version_label,
            status=rc.status.value,
            rules_json=rc.rules_json,
        )

    rc.status = RateCardVersionStatus.approved
    rc.approved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(rc)
    return RateCardOut(
        id=rc.id,
        carrier_code=rc.carrier_code,
        version_label=rc.version_label,
        status=rc.status.value,
        rules_json=rc.rules_json,
    )


class PartnerOnboardingPayload(BaseModel):
    partner_name: str | None = None
    branding_mode: str | None = None
    export_methods: list[str] = Field(default_factory=list)
    export_fields: dict | None = None
    carriers: list[str] = Field(default_factory=list)
    embed_mode: str | None = None
    ingest_mode: str | None = None
    is_3pl: bool | None = None
    notes: str | None = None


@router.get("/partners/{partner_id}/onboarding")
async def get_partner_onboarding(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    from app.services.partner_profiles import get_partner_profile

    return await get_partner_profile(db, partner_id)


@router.put("/partners/{partner_id}/onboarding")
async def save_partner_onboarding(
    partner_id: str,
    body: PartnerOnboardingPayload,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    from app.services.partner_profiles import upsert_partner_profile

    payload = body.model_dump(exclude_none=True)
    return await upsert_partner_profile(db, partner_id, payload)


@router.get("/organizations/{org_id}/client-onboarding")
async def get_client_onboarding(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_org: UUID = Depends(require_org_id),
) -> dict:
    from app.models import Organization

    if org_id != current_org:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Organization mismatch")
    await set_rls_organization(db, current_org)
    org = await db.scalar(select(Organization).where(Organization.id == current_org))
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Organization not found")
    return (org.settings_json or {}).get("client_onboarding", {})


class ClientOnboardingPayload(BaseModel):
    org_name: str | None = None
    export_method_override: str | None = None
    carriers: list[str] = Field(default_factory=list)
    tolerances: dict | None = None


@router.put("/organizations/{org_id}/client-onboarding")
async def save_client_onboarding(
    org_id: UUID,
    body: ClientOnboardingPayload,
    db: AsyncSession = Depends(get_db),
    current_org: UUID = Depends(require_org_id),
) -> dict:
    from app.models import Organization

    if org_id != current_org:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Organization mismatch")
    await set_rls_organization(db, current_org)
    org = await db.scalar(select(Organization).where(Organization.id == current_org))
    if not org:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Organization not found")
    settings = dict(org.settings_json or {})
    settings["client_onboarding"] = body.model_dump(exclude_none=True)
    org.settings_json = settings
    await db.commit()
    return settings["client_onboarding"]
