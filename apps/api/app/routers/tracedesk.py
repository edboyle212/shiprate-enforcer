"""TraceDesk queue, organization contacts, and claim packets. Confirm does not send."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_org_id
from app.db import get_db, set_rls_organization
from app.models import TraceDeskOrder
from app.services.tracedesk_cases import (
    EvidenceFile,
    EvidenceName,
    create_trace_case,
    import_contact_csv,
    import_order_csv,
    list_contacts,
    list_queue,
    load_org_contact,
    preview_trace,
)
from app.services.tracedesk_rules import (
    TraceRejected,
    canonical_carrier,
    rules_document,
)

router = APIRouter(prefix="/tracedesk")


class EvidenceIn(BaseModel):
    kind: str
    filename: str


class PreviewIn(BaseModel):
    tracking_reference: str
    reason: str
    length_in: float
    width_in: float
    height_in: float
    contents_summary: str
    order_reference: str
    evidence: list[EvidenceIn] = Field(default_factory=list)
    require_contact: bool = False


def _http_for(err: TraceRejected) -> HTTPException:
    codes = {error.code for error in err.errors}
    status = 409 if codes == {"case_exists"} else 422
    return HTTPException(status_code=status, detail={"errors": [error.as_dict() for error in err.errors]})


async def _order_or_404(db: AsyncSession, organization_id: UUID, order_id: UUID) -> TraceDeskOrder:
    order = await db.get(TraceDeskOrder, order_id)
    if order is None or order.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/rules")
async def get_rules(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    return rules_document()


@router.post("/orders/upload")
async def upload_orders(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    data = await file.read()
    try:
        return await import_order_csv(db, organization_id=org_id, filename=file.filename or "orders.csv", data=data)
    except TraceRejected as err:
        raise _http_for(err) from err


@router.get("/orders")
async def get_orders(
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    return await list_queue(db, org_id, q)


@router.post("/carrier-contacts/upload")
async def upload_contacts(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    data = await file.read()
    try:
        return await import_contact_csv(
            db,
            organization_id=org_id,
            filename=file.filename or "contacts.csv",
            data=data,
        )
    except TraceRejected as err:
        raise _http_for(err) from err


@router.get("/carrier-contacts")
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    return {"contacts": await list_contacts(db, org_id)}


@router.post("/orders/{order_id}/preview")
async def preview_order(
    order_id: UUID,
    body: PreviewIn,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    order = await _order_or_404(db, org_id, order_id)
    carrier = canonical_carrier(order.carrier_code)
    contact = None if carrier is None else await load_org_contact(db, org_id, carrier)
    try:
        return preview_trace(
            order=order,
            contact=contact,
            tracking_reference=body.tracking_reference,
            reason=body.reason,
            length_in=body.length_in,
            width_in=body.width_in,
            height_in=body.height_in,
            contents_summary=body.contents_summary,
            order_reference=body.order_reference,
            evidence=[EvidenceName(item.kind, item.filename) for item in body.evidence],
            as_of=date.today(),
            require_contact=body.require_contact,
        )
    except TraceRejected as err:
        raise _http_for(err) from err


async def _read_evidence(kind: str, upload: UploadFile | None) -> EvidenceFile | None:
    if upload is None:
        return None
    data = await upload.read()
    if not data:
        return None
    return EvidenceFile(
        kind=kind,
        filename=upload.filename or kind,
        content_type=upload.content_type,
        data=data,
    )


@router.post("/orders/{order_id}/confirm")
async def confirm_order(
    order_id: UUID,
    tracking_reference: str = Form(...),
    reason: str = Form(...),
    length_in: float = Form(...),
    width_in: float = Form(...),
    height_in: float = Form(...),
    contents_summary: str = Form(...),
    order_reference: str = Form(...),
    shipment_photo: UploadFile | None = File(None),
    sales_invoice: UploadFile | None = File(None),
    purchase_invoice: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(require_org_id),
) -> dict:
    await set_rls_organization(db, org_id)
    order = await _order_or_404(db, org_id, order_id)
    files = [
        item
        for item in (
            await _read_evidence("shipment_photo", shipment_photo),
            await _read_evidence("sales_invoice", sales_invoice),
            await _read_evidence("purchase_invoice", purchase_invoice),
        )
        if item is not None
    ]
    try:
        return await create_trace_case(
            db,
            organization_id=org_id,
            order=order,
            tracking_reference=tracking_reference,
            reason=reason,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            contents_summary=contents_summary,
            order_reference=order_reference,
            evidence_files=files,
            as_of=date.today(),
        )
    except TraceRejected as err:
        raise _http_for(err) from err
