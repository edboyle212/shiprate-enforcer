from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RateInput:
    dest_postal: str
    weight_oz: int
    service_code: str


@dataclass(frozen=True)
class RateResult:
    allowed_amount_minor: int
    currency_code: str
    trace: dict[str, Any]


def zone_from_postal(postal: str, zone_table: dict[str, int]) -> int:
    prefix = (postal or "")[:3]
    if prefix in zone_table:
        return zone_table[prefix]
    return int(zone_table.get("default", 8))


def rate_shipment(rules_json: dict[str, Any], inp: RateInput) -> RateResult:
    """
    Deterministic parcel rating: zone lookup + per-zone base rate + minimum charge.
    Money in minor units (cents).
    """
    currency = str(rules_json.get("currency_code", "USD"))
    zone_table = rules_json.get("zone_by_postal_prefix", {})
    zone_rates = rules_json.get("zone_rates_minor", {})
    minimum_minor = int(rules_json.get("minimum_charge_minor", 895))
    service_multiplier = float(rules_json.get("service_multipliers", {}).get(inp.service_code, 1.0))

    zone = zone_from_postal(inp.dest_postal, zone_table)
    base = int(zone_rates.get(str(zone), zone_rates.get("default", 1000)))
    weight_factor = max(1, (inp.weight_oz + 15) // 16)
    computed = int(base * weight_factor * service_multiplier)
    allowed = max(computed, minimum_minor)

    trace = {
        "steps": [
            {"step": "zone_lookup", "dest_postal": inp.dest_postal, "zone": zone},
            {"step": "base_rate_minor", "zone": zone, "base_minor": base},
            {"step": "weight_factor", "weight_oz": inp.weight_oz, "factor": weight_factor},
            {"step": "service_multiplier", "service_code": inp.service_code, "multiplier": service_multiplier},
            {"step": "minimum_charge", "minimum_minor": minimum_minor, "computed_minor": computed},
        ],
        "allowed_amount_minor": allowed,
        "currency_code": currency,
    }
    return RateResult(allowed_amount_minor=allowed, currency_code=currency, trace=trace)
