"""Deterministic parcel rating — golden contract (GND, zone table, minimum charge)."""

from __future__ import annotations

from typing import Any

ENGINE_VERSION = "0.1.0"


def _billable_weight_oz(request: dict[str, Any]) -> int:
    packages = request.get("packages") or []
    if not packages:
        return 1
    pkg = packages[0]
    actual = int(pkg.get("actual_weight_oz", 1))
    policy = request.get("policy") or {}
    if policy.get("billable_weight_source") != "max_actual_dim":
        return max(1, actual)
    length = float(pkg.get("length_in", 0))
    width = float(pkg.get("width_in", 0))
    height = float(pkg.get("height_in", 0))
    divisor = float(policy.get("dim_divisor", 139))
    if not divisor:
        return max(1, actual)
    dim_pounds = (length * width * height) / divisor
    if dim_pounds < 1:
        return max(1, actual)
    dim_weight_oz = int(dim_pounds * 16)
    return max(1, actual, dim_weight_oz)


def _zone_for_destination(request: dict[str, Any]) -> int:
    snapshot = request.get("rate_card_snapshot") or {}
    zones = snapshot.get("zones") or {}
    dest = str(request.get("destination_postal", ""))
    if dest in zones:
        return int(zones[dest])
    prefix = dest[:3]
    if prefix in zones:
        return int(zones[prefix])
    return int(zones.get("default", 8))


def rate(request: dict[str, Any]) -> dict[str, Any]:
    """
    Rate one shipment request. Money in minor units (USD cents).
    """
    service = str(request.get("service_level", "GND"))
    currency = str(request.get("currency_code", "USD"))
    snapshot = request.get("rate_card_snapshot") or {}
    weight_oz = _billable_weight_oz(request)
    zone = _zone_for_destination(request)

    table: dict[str, int] = snapshot.get("weight_break_table_minor") or {}
    table_key = f"{service}|{zone}|{weight_oz}oz"
    table_rate = int(table.get(table_key, table.get(f"{service}|{zone}|default", 0)))

    minimums = snapshot.get("minimum_charge_minor") or {}
    minimum = int(minimums.get(service, minimums.get("default", 0)))

    computed = table_rate
    minimum_applied = computed < minimum
    allowed = max(computed, minimum) if minimum else computed

    fuel_pct = float((request.get("policy") or {}).get("fuel_surcharge_pct", 0))
    if fuel_pct:
        allowed = int(allowed * (1 + fuel_pct))

    trace = {
        "engine_version": ENGINE_VERSION,
        "rate_card_version_id": request.get("rate_card_version_id"),
        "contract_version_id": request.get("contract_version_id"),
        "rules_evaluated": {
            "rule_bundle_hash": request.get("rule_bundle_hash"),
            "table_key": table_key,
            "table_rate_minor": table_rate,
            "minimum_charge_minor": minimum,
        },
        "zone": zone,
        "billable_weight_oz": weight_oz,
        "minimum_charge_applied": minimum_applied,
        "allowed_total_minor": allowed,
    }

    return {
        "allowed_total_minor": allowed,
        "currency_code": currency,
        "status": "OK",
        "trace": trace,
    }


def rate_shipment(request: dict[str, Any]) -> dict[str, Any]:
    return rate(request)


def replay(
    *,
    inputs: dict[str, Any],
    rule_bundle_hash: str,
    engine_version: str = ENGINE_VERSION,
) -> dict[str, Any]:
    payload = {**inputs, "rule_bundle_hash": rule_bundle_hash, "engine_version": engine_version}
    return rate(payload)
