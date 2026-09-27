"""AI column mapping — template fallback when AI disabled."""

from __future__ import annotations

import pytest

from app.services.ai_mapping import ai_runtime_enabled, resolve_mapping_without_ai


def test_ai_disabled_uses_template_mapping():
    headers = ["tracking_number", "carrier", "service", "dest_postal", "weight_oz"]
    mapping = resolve_mapping_without_ai(headers=headers, kind="shipment_export")
    assert mapping["tracking_number"] == "tracking_number"
    assert mapping["carrier_code"] == "carrier"
    assert mapping["service_code"] == "service"
    assert mapping["dest_postal"] == "dest_postal"
    assert mapping["weight_oz"] == "weight_oz"


def test_ai_runtime_disabled_without_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SHIPRATE_AI_ENABLED", raising=False)
    assert ai_runtime_enabled(org_flag=None) is False


def test_ai_runtime_enabled_requires_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHIPRATE_AI_ENABLED", "1")
    from app.config import settings

    monkeypatch.setattr(settings, "ai_jev_api_key", None, raising=False)
    monkeypatch.setattr(settings, "ai_grok_api_key", None, raising=False)
    monkeypatch.setattr(settings, "ai_claude_api_key", None, raising=False)
    assert ai_runtime_enabled(org_flag=True) is False

    monkeypatch.setattr(settings, "ai_claude_api_key", "test-key", raising=False)
    assert ai_runtime_enabled(org_flag=True) is True
