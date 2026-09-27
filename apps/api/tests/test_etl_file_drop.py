"""Unit tests for ETL file-drop adapter (filesystem backend)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.config import settings
from app.services.storage import storage_service


@pytest.mark.integration
def test_list_etl_objects_local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "local_upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "s3_endpoint_url", None)
    monkeypatch.setattr(settings, "etl_drop_root", "etl-drops")

    partner = "jasci"
    org = str(uuid.uuid4())
    ship_dir = tmp_path / "etl-drops" / partner / org / "shipments"
    ship_dir.mkdir(parents=True)
    (ship_dir / "export.csv").write_text("tracking_number,dest_postal\n1Z999,10001\n", encoding="utf-8")

    # Re-init storage to pick up settings
    from app.services import storage as storage_mod

    storage_mod.storage_service = storage_mod.StorageService()
    keys = storage_mod.storage_service.list_etl_objects(partner, org, "shipments")
    assert len(keys) == 1
    assert keys[0].endswith("export.csv")
    data = storage_mod.storage_service.read_object(keys[0])
    assert b"1Z999" in data
