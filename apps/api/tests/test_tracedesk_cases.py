"""TraceDesk queue, organization contacts, and the create-case path."""

from __future__ import annotations

import ast
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.models import (
    OrganizationCarrierContact,
    TraceDeskCase,
    TraceDeskClaimPacket,
    TraceDeskEvidence,
    TraceDeskOrder,
)
from app.services.tracedesk_cases import (
    EvidenceFile,
    EvidenceName,
    build_claim_email,
    build_queue_rows,
    create_trace_case,
    filter_rows,
    import_contact_csv,
    import_order_csv,
    inspect_evidence_files,
    list_queue,
    parse_contact_csv,
    parse_order_csv,
    preview_trace,
    summarize_counts,
)
from app.services.tracedesk_rules import TraceDetails, TraceRejected, validate_details

ORG = uuid.UUID("01950000-0000-7000-8000-000000000001")
UPS = "1Z999AA10123456784"
AS_OF = date(2026, 10, 13)
CONTACT_EMAIL = "avery@northwind.example"


class FakeSession:
    def __init__(self):
        self.orders_by_id: dict = {}
        self.orders: list = []
        self.cases: list = []
        self.contact = None
        self.contacts: list = []
        self.existing_order_ids: set[str] = set()
        self.added: list = []
        self.committed = False

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)
        if isinstance(obj, OrganizationCarrierContact):
            self.contacts.append(obj)
            self.contact = obj

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True

    async def execute(self, *_args, **_kwargs):
        return None

    async def get(self, model, ident):
        if model is TraceDeskOrder:
            return self.orders_by_id.get(ident)
        return None

    def _name(self, stmt) -> str:
        return " ".join(item.name for item in stmt.get_final_froms())

    async def scalar(self, stmt):
        name = self._name(stmt)
        if "organization_carrier_contacts" in name:
            return self.contact
        if "tracedesk_cases" in name:
            if not self.cases:
                return None
            return getattr(self.cases[0], "id", None) or uuid.uuid4()
        if "tracedesk_orders" in name:
            params = stmt.compile().params
            for key, value in params.items():
                if "external_order_id" in key and value in self.existing_order_ids:
                    return uuid.uuid4()
            return None
        return None

    async def scalars(self, stmt):
        name = self._name(stmt)
        if "tracedesk_cases" in name:
            rows = self.cases
        elif "organization_carrier_contacts" in name:
            rows = self.contacts
        else:
            rows = self.orders

        class _Result:
            def all(self):
                return list(rows)

        return _Result()


def _order(**overrides) -> TraceDeskOrder:
    payload = {
        "id": uuid.uuid4(),
        "organization_id": ORG,
        "external_order_id": "100245",
        "customer_name": "Ada Lovelace",
        "customer_email": "ada@analytical.example",
        "carrier_code": "UPS",
        "tracking_reference": UPS,
        "ship_date": date(2026, 10, 1),
    }
    payload.update(overrides)
    return TraceDeskOrder(**payload)


def _contact(**overrides) -> OrganizationCarrierContact:
    payload = {
        "id": uuid.uuid4(),
        "organization_id": ORG,
        "carrier_code": "UPS",
        "contact_name": "Avery Chen",
        "email": CONTACT_EMAIL,
        "account_reference": "ACCT-44",
    }
    payload.update(overrides)
    return OrganizationCarrierContact(**payload)


def _invoice() -> EvidenceFile:
    return EvidenceFile("sales_invoice", "invoice.pdf", "application/pdf", b"%PDF-1.4 invoice")


def _photo() -> EvidenceFile:
    return EvidenceFile("shipment_photo", "damage.png", "image/png", b"\x89PNG\r\n")


def _put(org, filename, data):
    return (f"{org}/{filename}", "abc123")


def test_tracedesk_sources_do_not_call_mail_or_platform_contacts():
    root = Path(__file__).resolve().parents[1] / "app"
    paths = [
        root / "services" / "tracedesk_rules.py",
        root / "services" / "tracedesk_cases.py",
        root / "routers" / "tracedesk.py",
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for name in modules:
                parts = name.split(".")
                assert "mail" not in parts
                assert "carrier_contacts" not in parts
                assert "resend" not in name
        text = path.read_text(encoding="utf-8")
        assert "carrier.test" not in text
        assert "billing-" not in text


def test_order_csv_keeps_shipped_rows_and_reports_bad_ones():
    parsed = parse_order_csv(
        "order_id,customer_name,customer_email,carrier,tracking_reference,ship_date\n"
        "100245,Ada Lovelace,ada@analytical.example,UPS,1Z999AA10123456784,2026-10-01\n"
        "100245,Ada Lovelace,ada@analytical.example,UPS,1Z999AA10123456784,2026-10-01\n"
        "100246,Grace Hopper,grace@navy.example,DHL,123,2026-10-01\n"
        "100247,No Date,nodate@example.com,FedEx,123456789012,10/01/2026\n"
    )
    assert parsed.header_error is False
    assert len(parsed.orders) == 1
    assert parsed.orders[0].carrier_code == "UPS"
    assert parsed.orders[0].customer_email == "ada@analytical.example"
    messages = " ".join(str(error["message"]) for error in parsed.errors)
    assert "Duplicate" in messages
    assert "UPS, FedEx, or USPS" in messages
    assert "YYYY-MM-DD" in messages
    empty = parse_order_csv("carrier,contact_name\n")
    assert empty.header_error is True


def test_contact_csv_requires_name_email_and_carrier():
    parsed = parse_contact_csv(
        "carrier,contact_name,email,account_reference\n"
        "FedEx,Riley Quinn,riley@northwind.example,FX-19\n"
        "ups,,avery@northwind.example,\n"
        "USPS,Sam Patel,not-an-email,PO-1\n"
    )
    assert len(parsed.contacts) == 1
    assert parsed.contacts[0].carrier_code == "FEDEX"
    assert parsed.contacts[0].email == "riley@northwind.example"
    assert parsed.contacts[0].account_reference == "FX-19"
    messages = " ".join(str(error["message"]) for error in parsed.errors)
    assert "Contact name" in messages
    assert "Contact email" in messages


@pytest.mark.asyncio
async def test_import_orders_skips_existing_and_rejects_a_bad_header(monkeypatch):
    monkeypatch.setattr("app.services.tracedesk_cases.storage_service.put_immutable", _put)
    session = FakeSession()
    session.existing_order_ids.add("100245")
    csv_text = (
        "order_id,customer_name,customer_email,carrier,tracking_reference,ship_date\n"
        "100245,Ada Lovelace,ada@analytical.example,UPS,1Z999AA10123456784,2026-10-01\n"
        "100248,Grace Hopper,grace@navy.example,FedEx,123456789012,2026-10-02\n"
    )
    result = await import_order_csv(session, organization_id=ORG, filename="orders.csv", data=csv_text.encode())
    assert result["created"] == 1
    assert result["skipped"] == 1
    assert session.committed is True
    assert any(isinstance(item, TraceDeskOrder) and item.external_order_id == "100248" for item in session.added)

    with pytest.raises(TraceRejected):
        await import_order_csv(session, organization_id=ORG, filename="bad.csv", data=b"order_id\n1\n")


@pytest.mark.asyncio
async def test_import_contacts_updates_an_existing_organization_row(monkeypatch):
    monkeypatch.setattr("app.services.tracedesk_cases.storage_service.put_immutable", _put)
    session = FakeSession()
    session.contact = _contact(email="old@northwind.example", contact_name="Old Name")
    csv_text = (
        "carrier,contact_name,email,account_reference\n"
        "UPS,Avery Chen,avery@northwind.example,ACCT-44\n"
    )
    result = await import_contact_csv(session, organization_id=ORG, filename="contacts.csv", data=csv_text.encode())
    assert result["created"] == 0
    assert result["updated"] == 1
    assert session.contact.email == CONTACT_EMAIL
    assert session.contact.contact_name == "Avery Chen"
    assert session.contact.account_reference == "ACCT-44"


@pytest.mark.asyncio
async def test_queue_counts_cover_the_book_and_search_ignores_tracking():
    ready = _order(external_order_id="100245", customer_name="Ada Lovelace", customer_email="ada@analytical.example")
    live_order = _order(external_order_id="100246", customer_name="Grace Hopper", customer_email="grace@navy.example")
    waiting_order = _order(external_order_id="100247", customer_name="Katherine Johnson", customer_email="kj@nasa.example")
    resolved_order = _order(external_order_id="100248", customer_name="Margaret Hamilton", customer_email="mh@mit.example")
    live = TraceDeskCase(
        id=uuid.uuid4(),
        organization_id=ORG,
        order_id=live_order.id,
        carrier_code="UPS",
        tracking_reference=UPS,
        reason="loss",
        length_in=1,
        width_in=1,
        height_in=1,
        contents_summary="books",
        order_reference="100246",
        ship_date=live_order.ship_date,
        status="open",
    )
    waiting = TraceDeskCase(
        id=uuid.uuid4(),
        organization_id=ORG,
        order_id=waiting_order.id,
        carrier_code="UPS",
        tracking_reference="TRACK-ONLY",
        reason="damage",
        length_in=1,
        width_in=1,
        height_in=1,
        contents_summary="books",
        order_reference="100247",
        ship_date=waiting_order.ship_date,
        status="awaiting_carrier",
    )
    resolved = TraceDeskCase(
        id=uuid.uuid4(),
        organization_id=ORG,
        order_id=resolved_order.id,
        carrier_code="UPS",
        tracking_reference=UPS,
        reason="loss",
        length_in=1,
        width_in=1,
        height_in=1,
        contents_summary="books",
        order_reference="100248",
        ship_date=resolved_order.ship_date,
        status="resolved",
    )
    session = FakeSession()
    session.orders = [ready, live_order, waiting_order, resolved_order]
    session.cases = [live, waiting, resolved]
    listed = await list_queue(session, ORG, "TRACK-ONLY")
    assert listed["counts"] == {
        "ready_to_review": 1,
        "live_investigations": 1,
        "awaiting_carrier": 1,
    }
    assert listed["orders"] == []
    by_email = await list_queue(session, ORG, "grace@navy.example")
    assert [row["external_order_id"] for row in by_email["orders"]] == ["100246"]
    assert by_email["counts"]["ready_to_review"] == 1
    found = await list_queue(session, ORG, "katherine")
    assert found["orders"][0]["external_order_id"] == "100247"
    assert found["orders"][0]["case_status"] == "awaiting_carrier"


def test_summarize_counts_ignores_resolved_rows():
    rows = []
    counts = summarize_counts(rows)
    assert counts == {"ready_to_review": 0, "live_investigations": 0, "awaiting_carrier": 0}


@pytest.mark.asyncio
async def test_create_case_stores_packet_for_the_uploaded_contact_and_does_not_send(monkeypatch):
    monkeypatch.setattr("app.services.tracedesk_cases.storage_service.put_immutable", _put)

    def _boom(*_args, **_kwargs):
        raise AssertionError("platform mail or carrier contact was used")

    from app.services import carrier_contacts as platform_contacts
    from app.services import mail

    monkeypatch.setattr(platform_contacts, "resolve_carrier_email", _boom)
    monkeypatch.setattr(mail, "get_mail_sender", _boom)

    session = FakeSession()
    session.contact = _contact()
    order = _order()
    result = await create_trace_case(
        session,
        organization_id=ORG,
        order=order,
        tracking_reference="https://www.ups.com/track?tracknum=1Z999AA10123456784",
        reason="loss",
        length_in=10,
        width_in=8,
        height_in=4,
        contents_summary="Two linen shirts",
        order_reference="100245",
        evidence_files=[_invoice(), EvidenceFile("purchase_invoice", "po.pdf", "application/pdf", b"%PDF po")],
        as_of=AS_OF,
    )
    assert result["email_sent"] is False
    assert result["status"] == "open"
    packet = result["packet"]
    assert packet["email_sent"] is False
    assert packet["channel"] == "claim_packet"
    assert packet["recipient"]["email"] == CONTACT_EMAIL
    assert packet["recipient"]["contact_name"] == "Avery Chen"
    assert packet["recipient"]["account_reference"] == "ACCT-44"
    assert "This email was not sent." in packet["email_body"]
    assert f"Recipient: Avery Chen <{CONTACT_EMAIL}>" in packet["email_body"]
    assert "carrier.test" not in packet["email_body"]
    assert session.committed is True
    saved = [item for item in session.added if isinstance(item, TraceDeskClaimPacket)]
    assert saved[0].recipient_address == CONTACT_EMAIL
    assert saved[0].email_sent is False
    assert any(isinstance(item, TraceDeskCase) and item.status == "open" for item in session.added)
    assert sum(isinstance(item, TraceDeskEvidence) for item in session.added) == 2


@pytest.mark.asyncio
async def test_create_case_rejects_a_closed_window_a_bad_reference_or_missing_evidence(monkeypatch):
    calls = {"n": 0}

    def _put_count(*_args, **_kwargs):
        calls["n"] += 1
        return ("key", "abc")

    monkeypatch.setattr("app.services.tracedesk_cases.storage_service.put_immutable", _put_count)
    session = FakeSession()
    session.contact = _contact()
    order = _order(ship_date=date(2026, 1, 1))
    with pytest.raises(TraceRejected) as closed:
        await create_trace_case(
            session,
            organization_id=ORG,
            order=order,
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert any(error.code == "window_closed" for error in closed.value.errors)
    assert calls["n"] == 0
    assert session.committed is False

    session.added.clear()
    with pytest.raises(TraceRejected) as bad_ref:
        await create_trace_case(
            session,
            organization_id=ORG,
            order=_order(),
            tracking_reference="NOT-A-TRACKING",
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert any(error.code == "invalid_reference" for error in bad_ref.value.errors)
    assert calls["n"] == 0

    with pytest.raises(TraceRejected) as damage:
        await create_trace_case(
            session,
            organization_id=ORG,
            order=_order(),
            tracking_reference=UPS,
            reason="damage",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert any(error.code == "missing_evidence" for error in damage.value.errors)

    created = await create_trace_case(
        session,
        organization_id=ORG,
        order=_order(),
        tracking_reference=UPS,
        reason="damage",
        length_in=10,
        width_in=8,
        height_in=4,
        contents_summary="Shirts",
        order_reference="100245",
        evidence_files=[_invoice(), _photo()],
        as_of=AS_OF,
    )
    assert created["email_sent"] is False
    assert {item["kind"] for item in created["packet"]["evidence"]} == {"sales_invoice", "shipment_photo"}


@pytest.mark.asyncio
async def test_create_case_requires_the_organization_contact_for_the_order_carrier(monkeypatch):
    monkeypatch.setattr("app.services.tracedesk_cases.storage_service.put_immutable", _put)
    session = FakeSession()
    with pytest.raises(TraceRejected) as missing:
        await create_trace_case(
            session,
            organization_id=ORG,
            order=_order(),
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert any(error.code == "missing_carrier_contact" for error in missing.value.errors)
    assert session.committed is False
    assert not any(isinstance(item, TraceDeskCase) for item in session.added)

    session.cases = [object()]
    session.contact = _contact()
    with pytest.raises(TraceRejected) as exists:
        await create_trace_case(
            session,
            organization_id=ORG,
            order=_order(),
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert exists.value.errors[0].code == "case_exists"


def test_preview_uses_the_uploaded_contact_and_blocks_recap_without_one():
    order = _order()
    ready = preview_trace(
        order=order,
        contact=_contact(),
        tracking_reference=UPS,
        reason="loss",
        length_in=10,
        width_in=8,
        height_in=4,
        contents_summary="Shirts",
        order_reference="100245",
        evidence=[EvidenceName("sales_invoice", "invoice.pdf")],
        as_of=AS_OF,
        require_contact=True,
    )
    assert ready["email_sent"] is False
    assert ready["contact_ready"] is True
    assert ready["recipient"]["email"] == CONTACT_EMAIL
    assert CONTACT_EMAIL in ready["email_body"]

    with pytest.raises(TraceRejected) as missing:
        preview_trace(
            order=order,
            contact=None,
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence=[EvidenceName("sales_invoice", "invoice.pdf")],
            as_of=AS_OF,
            require_contact=True,
        )
    assert any(error.code == "missing_carrier_contact" for error in missing.value.errors)

    details_only = preview_trace(
        order=order,
        contact=None,
        tracking_reference=UPS,
        reason="loss",
        length_in=10,
        width_in=8,
        height_in=4,
        contents_summary="Shirts",
        order_reference="100245",
        evidence=[],
        as_of=AS_OF,
        require_contact=False,
    )
    assert details_only["contact_ready"] is False
    assert details_only["email_body"] is None


class _MiddlewareSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


@pytest.fixture
def tracedesk_client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.db import get_db
    from app.main import app
    from tests.db import admin_auth_headers

    monkeypatch.setattr(settings, "env", "test")
    monkeypatch.setattr("app.middleware.auth.SessionLocal", lambda: _MiddlewareSession())
    monkeypatch.setattr("app.services.tracedesk_cases.storage_service.put_immutable", _put)
    fake = FakeSession()

    async def _db():
        yield fake

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    client.headers.update({"X-Organization-Id": str(ORG)})
    client.headers.update(admin_auth_headers(org_id=ORG))
    yield client, fake
    app.dependency_overrides.clear()


def test_confirm_route_saves_packet_without_sending(tracedesk_client):
    client, fake = tracedesk_client
    order = _order(ship_date=date.today() - timedelta(days=3))
    fake.orders_by_id[order.id] = order
    fake.contact = _contact()
    response = client.post(
        f"/api/v1/tracedesk/orders/{order.id}/confirm",
        data={
            "tracking_reference": UPS,
            "reason": "loss",
            "length_in": "10",
            "width_in": "8",
            "height_in": "4",
            "contents_summary": "Two linen shirts",
            "order_reference": "100245",
        },
        files={"sales_invoice": ("invoice.pdf", b"%PDF-1.4 invoice", "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email_sent"] is False
    assert body["packet"]["recipient"]["email"] == CONTACT_EMAIL
    assert "This email was not sent." in body["packet"]["email_body"]


def test_confirm_route_blocks_a_missing_contact(tracedesk_client):
    client, fake = tracedesk_client
    order = _order(ship_date=date.today() - timedelta(days=3))
    fake.orders_by_id[order.id] = order
    response = client.post(
        f"/api/v1/tracedesk/orders/{order.id}/confirm",
        data={
            "tracking_reference": UPS,
            "reason": "loss",
            "length_in": "10",
            "width_in": "8",
            "height_in": "4",
            "contents_summary": "Two linen shirts",
            "order_reference": "100245",
        },
        files={"sales_invoice": ("invoice.pdf", b"%PDF-1.4 invoice", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["code"] == "missing_carrier_contact"


def test_tracedesk_routes_list_rules_orders_and_contacts(tracedesk_client):
    client, fake = tracedesk_client
    rules = client.get("/api/v1/tracedesk/rules")
    assert rules.status_code == 200
    assert rules.json()["email_sent_on_confirm"] is False

    order = _order()
    fake.orders = [order]
    listed = client.get("/api/v1/tracedesk/orders", params={"q": "ada"})
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["counts"]["ready_to_review"] == 1
    assert payload["orders"][0]["customer_email"] == "ada@analytical.example"

    uploaded = client.post(
        "/api/v1/tracedesk/carrier-contacts/upload",
        files={
            "file": (
                "contacts.csv",
                b"carrier,contact_name,email,account_reference\nUPS,Avery Chen,avery@northwind.example,ACCT-44\n",
                "text/csv",
            )
        },
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["created"] == 1
    contacts = client.get("/api/v1/tracedesk/carrier-contacts")
    assert contacts.status_code == 200
    assert contacts.json()["contacts"][0]["email"] == CONTACT_EMAIL

    bad_contacts = client.post(
        "/api/v1/tracedesk/carrier-contacts/upload",
        files={"file": ("contacts.csv", b"carrier\nUPS\n", "text/csv")},
    )
    assert bad_contacts.status_code == 422

    order.ship_date = date.today() - timedelta(days=2)
    fake.orders_by_id[order.id] = order
    fake.contact = _contact()
    preview = client.post(
        f"/api/v1/tracedesk/orders/{order.id}/preview",
        json={
            "tracking_reference": UPS,
            "reason": "loss",
            "length_in": 10,
            "width_in": 8,
            "height_in": 4,
            "contents_summary": "Shirts",
            "order_reference": "100245",
            "evidence": [{"kind": "sales_invoice", "filename": "invoice.pdf"}],
            "require_contact": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["email_sent"] is False
    assert preview.json()["recipient"]["email"] == CONTACT_EMAIL

    rejected = client.post(
        f"/api/v1/tracedesk/orders/{order.id}/preview",
        json={
            "tracking_reference": "NOT-A-TRACKING",
            "reason": "loss",
            "length_in": 10,
            "width_in": 8,
            "height_in": 4,
            "contents_summary": "Shirts",
            "order_reference": "100245",
            "require_contact": False,
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["errors"][0]["code"] == "invalid_reference"

    missing = client.post(
        f"/api/v1/tracedesk/orders/{uuid.uuid4()}/confirm",
        data={
            "tracking_reference": UPS,
            "reason": "loss",
            "length_in": "10",
            "width_in": "8",
            "height_in": "4",
            "contents_summary": "Shirts",
            "order_reference": "100245",
        },
    )
    assert missing.status_code == 404

    bad_orders = client.post(
        "/api/v1/tracedesk/orders/upload",
        files={"file": ("orders.csv", b"order_id\n1\n", "text/csv")},
    )
    assert bad_orders.status_code == 422


def test_csv_parsers_report_blank_incomplete_and_overlong_rows():
    empty_orders = parse_order_csv("   ")
    assert empty_orders.header_error is True
    assert "empty" in str(empty_orders.errors[0]["message"]).lower()

    orders = parse_order_csv(
        "order_id,customer_name,customer_email,carrier,tracking_reference,ship_date\n"
        ",,,,,\n"
        ",Ada Lovelace,ada@analytical.example,UPS,1Z999AA10123456784,2026-10-01\n"
        "100248,,ada@analytical.example,UPS,1Z999AA10123456784,2026-10-01\n"
        "100249,Ada Lovelace,not-an-email,UPS,1Z999AA10123456784,2026-10-01\n"
        "100250,Ada Lovelace,ada@analytical.example,UPS,,2026-10-01\n"
        "100251,Ada Lovelace,ada@analytical.example,UPS,1Z999AA10123456784,2026-02-31\n"
    )
    assert orders.orders == []
    messages = " ".join(str(error["message"]) for error in orders.errors)
    assert "Order id is required" in messages
    assert "Customer name is required" in messages
    assert "Customer email" in messages
    assert "Tracking reference is required" in messages
    assert "real calendar date" in messages

    empty_contacts = parse_contact_csv("")
    assert empty_contacts.header_error is True
    long_name = "A" * 256
    long_account = "B" * 129
    contacts = parse_contact_csv(
        "carrier,contact_name,email,account_reference\n"
        ",,,\n"
        "DHL,Riley Quinn,riley@northwind.example,\n"
        "UPS,Avery Chen,avery@northwind.example,ACCT-44\n"
        "ups,Second Person,second@northwind.example,\n"
        f"FEDEX,{long_name},riley@northwind.example,\n"
        f"USPS,Sam Patel,sam@northwind.example,{long_account}\n"
    )
    assert [row.carrier_code for row in contacts.contacts] == ["UPS"]
    contact_messages = " ".join(str(error["message"]) for error in contacts.errors)
    assert "UPS, FedEx, or USPS" in contact_messages
    assert "Duplicate UPS" in contact_messages
    assert "255 characters" in contact_messages
    assert "128 characters" in contact_messages


def test_evidence_files_keep_a_pdf_by_extension_and_reject_the_rest():
    kept, errors = inspect_evidence_files(
        [
            EvidenceFile("mystery", "x.bin", "application/octet-stream", b"x"),
            EvidenceFile("shipment_photo", "box.png", "image/png", b"png"),
            EvidenceFile("shipment_photo", "again.png", "image/png", b"png"),
            EvidenceFile("sales_invoice", "empty.pdf", "application/pdf", b""),
            EvidenceFile("purchase_invoice", "big.pdf", "application/pdf", b"x" * 8_000_001),
            EvidenceFile("sales_invoice", "invoice.PDF", "application/octet-stream", b"%PDF"),
        ]
    )
    assert [item.filename for item in kept] == ["box.png", "invoice.PDF"]
    assert kept[1].content_type == "application/pdf"
    messages = " ".join(error.message for error in errors)
    assert "Unknown evidence" in messages
    assert "Only one shipment photo" in messages
    assert "larger than 8 MB" in messages
    _rejected, type_errors = inspect_evidence_files(
        [EvidenceFile("sales_invoice", "notes.txt", "text/plain", b"hi")]
    )
    assert "must be a photo or PDF" in type_errors[0].message
    accepted, detail_errors = validate_details(
        TraceDetails(
            carrier="UPS",
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            ship_date=date(2026, 10, 1),
        ),
        as_of=AS_OF,
    )
    assert detail_errors == []
    assert accepted is not None
    _subject, body = build_claim_email(accepted=accepted, evidence=[], contact=_contact())
    assert "none attached" in body


@pytest.mark.asyncio
async def test_imports_reject_empty_and_non_utf8_files():
    with pytest.raises(TraceRejected) as empty_orders:
        await import_order_csv(FakeSession(), organization_id=ORG, filename="orders.csv", data=b"")
    assert empty_orders.value.errors[0].code == "invalid_csv"
    with pytest.raises(TraceRejected) as bad_orders:
        await import_order_csv(FakeSession(), organization_id=ORG, filename="orders.csv", data=b"\xff\xfe")
    assert "UTF-8" in bad_orders.value.errors[0].message
    with pytest.raises(TraceRejected) as empty_contacts:
        await import_contact_csv(FakeSession(), organization_id=ORG, filename="", data=b"")
    assert empty_contacts.value.errors[0].code == "invalid_csv"


def test_queue_filter_returns_every_row_when_the_search_is_blank():
    rows = summarize_counts([])
    assert rows == {"ready_to_review": 0, "live_investigations": 0, "awaiting_carrier": 0}
    order = _order()
    queued = build_queue_rows([order], [])
    assert filter_rows(queued, "  ") == queued


def test_preview_and_create_reject_a_carrier_or_ship_date_the_order_does_not_have():
    unknown = _order(carrier_code="DHL")
    with pytest.raises(TraceRejected) as preview_unknown:
        preview_trace(
            order=unknown,
            contact=None,
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence=[],
            as_of=AS_OF,
            require_contact=False,
        )
    assert preview_unknown.value.errors[0].code == "unknown_carrier"

    undated = _order(ship_date=None)
    with pytest.raises(TraceRejected) as preview_undated:
        preview_trace(
            order=undated,
            contact=_contact(),
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence=[],
            as_of=AS_OF,
            require_contact=False,
        )
    assert preview_undated.value.errors[0].code == "missing_field"


@pytest.mark.asyncio
async def test_create_case_rejects_the_wrong_organization_or_a_missing_ship_date():
    with pytest.raises(TraceRejected) as wrong_org:
        await create_trace_case(
            FakeSession(),
            organization_id=uuid.uuid4(),
            order=_order(),
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert wrong_org.value.errors[0].code == "wrong_organization"

    with pytest.raises(TraceRejected) as unknown:
        await create_trace_case(
            FakeSession(),
            organization_id=ORG,
            order=_order(carrier_code="DHL"),
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert unknown.value.errors[0].code == "unknown_carrier"

    with pytest.raises(TraceRejected) as undated:
        await create_trace_case(
            FakeSession(),
            organization_id=ORG,
            order=_order(ship_date=None),
            tracking_reference=UPS,
            reason="loss",
            length_in=10,
            width_in=8,
            height_in=4,
            contents_summary="Shirts",
            order_reference="100245",
            evidence_files=[_invoice()],
            as_of=AS_OF,
        )
    assert undated.value.errors[0].code == "missing_field"
