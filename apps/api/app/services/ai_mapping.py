"""AI-assisted column mapping — feature-flagged, never touches rate tables."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ai_enabled_globally, settings
from app.models import AiDecisionRequest, AiDecisionResult, AiFeatureFlag

SHIPMENT_TEMPLATE = {
    "tracking_number": "tracking_number",
    "carrier_code": "carrier",
    "service_code": "service",
    "dest_postal": "dest_postal",
    "weight_oz": "weight_oz",
}

INVOICE_TEMPLATE = {
    "tracking_number": "tracking_number",
    "charge_code": "charge_code",
    "description": "description",
    "billed_amount": "billed_amount",
}

FEATURE_COLUMN_MAPPING = "column_mapping_ai"


class CompletionClient(Protocol):
    def complete_json(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]: ...


class StubCompletionClient:
    """Mock provider — logs intent without external HTTP when keys are absent."""

    provider_name = "stub"

    def complete_json(self, *, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        headers: list[str] = list(context.get("headers") or [])
        lowered = {h.lower(): h for h in headers}
        template = context.get("template") or {}
        mapping: dict[str, str] = {}
        for field, default_col in template.items():
            key = default_col.lower()
            mapping[field] = lowered.get(key, default_col)
        return {"mapping": mapping, "provider": self.provider_name, "prompt_excerpt": prompt[:120]}


def default_template_for_kind(kind: str) -> dict[str, str]:
    if kind == "carrier_invoice":
        return dict(INVOICE_TEMPLATE)
    return dict(SHIPMENT_TEMPLATE)


def ai_runtime_enabled(*, org_flag: bool | None) -> bool:
    if org_flag is False:
        return False
    if not ai_enabled_globally():
        return False
    if not (settings.ai_jev_api_key or settings.ai_grok_api_key or settings.ai_claude_api_key):
        return False
    return True


def resolve_mapping_without_ai(*, headers: list[str], kind: str) -> dict[str, str]:
    template = default_template_for_kind(kind)
    lowered = {h.lower(): h for h in headers}
    out: dict[str, str] = {}
    for field, default_col in template.items():
        out[field] = lowered.get(default_col.lower(), default_col)
    return out


@dataclass
class MapColumnsResult:
    mapping: dict[str, str]
    used_ai: bool
    provider: str | None
    request_id: uuid.UUID | None


async def org_ai_flag(session: AsyncSession, organization_id: uuid.UUID) -> bool | None:
    row = await session.scalar(
        select(AiFeatureFlag).where(
            AiFeatureFlag.organization_id == organization_id,
            AiFeatureFlag.feature_key == FEATURE_COLUMN_MAPPING,
        )
    )
    if row is None:
        return None
    return bool(row.enabled)


async def map_columns(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    headers: list[str],
    kind: str = "shipment_export",
    client: CompletionClient | None = None,
) -> MapColumnsResult:
    template = default_template_for_kind(kind)
    org_flag = await org_ai_flag(session, organization_id)
    use_ai = ai_runtime_enabled(org_flag=org_flag)

    request = AiDecisionRequest(
        organization_id=organization_id,
        decision_type="map_columns",
        input_json={"headers": headers, "kind": kind},
        provider=None,
    )
    session.add(request)
    await session.flush()

    mapping: dict[str, str]
    used_ai = False
    provider: str | None = None

    if use_ai:
        completion = client or StubCompletionClient()
        provider = getattr(completion, "provider_name", "stub")
        request.provider = provider
        raw = completion.complete_json(
            prompt="Map CSV headers to Shiprate import fields. Never set monetary amounts.",
            context={"headers": headers, "template": template, "kind": kind},
        )
        mapping = dict(raw.get("mapping") or resolve_mapping_without_ai(headers=headers, kind=kind))
        used_ai = True
        output = {"mapping": mapping, "raw": raw}
    else:
        mapping = resolve_mapping_without_ai(headers=headers, kind=kind)
        output = {"mapping": mapping, "source": "template"}

    result = AiDecisionResult(
        organization_id=organization_id,
        request_id=request.id,
        output_json=output,
        used_ai=used_ai,
    )
    session.add(result)
    await session.flush()

    return MapColumnsResult(
        mapping=mapping,
        used_ai=used_ai,
        provider=provider,
        request_id=request.id,
    )
