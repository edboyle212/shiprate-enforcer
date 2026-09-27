"""AI mapping stub path persists ai_decision_results (not covered by test_ai_mapping.py)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.models import AiDecisionRequest, AiDecisionResult
from app.services.ai_mapping import StubCompletionClient, map_columns

ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000001")


@pytest.mark.asyncio
async def test_map_columns_with_ai_stub_logs_ai_decision_results(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SHIPRATE_AI_ENABLED", "1")
    monkeypatch.setattr(settings, "ai_claude_api_key", "test-key", raising=False)

    session = AsyncMock()
    session.scalar.return_value = SimpleNamespace(enabled=True)
    added: list[object] = []

    def _add(obj: object) -> None:
        added.append(obj)
        if isinstance(obj, AiDecisionRequest) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    session.add = _add
    session.flush = AsyncMock()

    headers = ["tracking_number", "carrier", "service", "dest_postal", "weight_oz"]
    result = await map_columns(
        session,
        organization_id=ORG_ID,
        headers=headers,
        kind="shipment_export",
        client=StubCompletionClient(),
    )

    assert result.used_ai is True
    assert result.request_id is not None

    requests = [o for o in added if isinstance(o, AiDecisionRequest)]
    results = [o for o in added if isinstance(o, AiDecisionResult)]
    assert len(requests) == 1
    assert len(results) == 1
    assert results[0].used_ai is True
    assert results[0].request_id == requests[0].id
    assert "mapping" in (results[0].output_json or {})
