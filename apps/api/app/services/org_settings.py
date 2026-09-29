"""Organization settings for negotiation autonomy and platform fee."""

from __future__ import annotations

from sqlalchemy.orm.attributes import flag_modified

VALID_AUTONOMY_TIERS = frozenset({"draft", "approve_each", "autonomous"})
VALID_PEOPLE_ROLES = frozenset({"owner", "admin", "billing", "viewer"})
DEFAULT_AUTONOMY_TIER = "draft"
DEFAULT_RECOVERY_FEE_BPS = 2000
DEFAULT_ABSOLUTE_TOLERANCE_MINOR = 500
DEFAULT_PERCENT_TOLERANCE = 2.0
CLIENT_SETTINGS_KEYS: frozenset[str] = frozenset()
CONTACT_KEYS = ("primary_name", "primary_email", "billing_email", "disputes_email")


def autonomy_tier_from_settings(settings_json: dict[str, Any] | None) -> str:
    raw = (settings_json or {}).get("autonomy_tier", DEFAULT_AUTONOMY_TIER)
    if raw not in VALID_AUTONOMY_TIERS:
        return DEFAULT_AUTONOMY_TIER
    return str(raw)


def recovery_fee_bps_from_settings(settings_json: dict[str, Any] | None) -> int:
    raw = (settings_json or {}).get("recovery_fee_bps", DEFAULT_RECOVERY_FEE_BPS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RECOVERY_FEE_BPS
    if value < 0 or value > 10_000:
        return DEFAULT_RECOVERY_FEE_BPS
    return value


def carrier_billing_email(settings_json: dict[str, Any] | None, carrier_code: str | None) -> str | None:
    """Deprecated — use resolve_carrier_email(session, carrier_code)."""
    return None


def merge_client_settings(current: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply client-editable keys only. recovery_fee_bps is never taken from the client."""
    merged = dict(current or {})
    for blocked in ("autonomy_tier", "carrier_billing_emails", "recovery_fee_bps"):
        patch.pop(blocked, None)
    return merged


def apply_platform_recovery_fee(current: dict[str, Any] | None, fee_bps: int) -> dict[str, Any]:
    if fee_bps < 0 or fee_bps > 10_000:
        raise ValueError("invalid_recovery_fee_bps")
    merged = dict(current or {})
    merged["recovery_fee_bps"] = fee_bps
    return merged


def _onboarding(settings: dict[str, Any]) -> dict[str, Any]:
    raw = settings.get("client_onboarding")
    return dict(raw) if isinstance(raw, dict) else {}


def _contacts(settings: dict[str, Any]) -> dict[str, str]:
    raw = settings.get("contacts")
    source = raw if isinstance(raw, dict) else {}
    return {key: str(source.get(key) or "") for key in CONTACT_KEYS}


def profile_from_org(org: Any) -> dict[str, Any]:
    settings = dict(org.settings_json or {})
    onboarding = _onboarding(settings)
    raw_tol = onboarding.get("tolerances") if isinstance(onboarding.get("tolerances"), dict) else {}
    try:
        absolute = int(raw_tol.get("absolute_minor", DEFAULT_ABSOLUTE_TOLERANCE_MINOR))
    except (TypeError, ValueError):
        absolute = DEFAULT_ABSOLUTE_TOLERANCE_MINOR
    try:
        percent = float(raw_tol.get("percent", DEFAULT_PERCENT_TOLERANCE))
    except (TypeError, ValueError):
        percent = DEFAULT_PERCENT_TOLERANCE
    people = settings.get("people") if isinstance(settings.get("people"), list) else []
    emails = settings.get("carrier_billing_emails")
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "partner_id": org.partner_id,
        "contacts": _contacts(settings),
        "people": people,
        "carriers": list(onboarding.get("carriers") or []) if isinstance(onboarding.get("carriers"), list) else [],
        "tolerances": {"absolute_minor": absolute, "percent": percent},
        "autonomy_tier": autonomy_tier_from_settings(settings),
        "carrier_billing_emails": dict(emails) if isinstance(emails, dict) else {},
        "recovery_fee_bps": recovery_fee_bps_from_settings(settings),
        "setup_complete": bool(onboarding.get("completed_at")),
    }


def apply_profile_patch(org: Any, patch: dict[str, Any]) -> Any:
    """Apply client-owned profile fields. Ignores recovery_fee_bps."""
    settings = dict(org.settings_json or {})
    name = patch.get("name")
    if isinstance(name, str) and name.strip():
        org.name = name.strip()

    client_patch: dict[str, Any] = {}
    patch.pop("autonomy_tier", None)
    patch.pop("carrier_billing_emails", None)
    if client_patch:
        settings = merge_client_settings(settings, client_patch)

    if patch.get("contacts") is not None:
        contacts = patch["contacts"]
        if not isinstance(contacts, dict):
            raise ValueError("invalid_contacts")
        settings["contacts"] = {key: str(contacts.get(key) or "") for key in CONTACT_KEYS}

    if patch.get("people") is not None:
        people = patch["people"]
        if not isinstance(people, list):
            raise ValueError("invalid_people")
        cleaned: list[dict[str, str]] = []
        for row in people:
            if not isinstance(row, dict):
                raise ValueError("invalid_people")
            role = str(row.get("role") or "viewer")
            if role not in VALID_PEOPLE_ROLES:
                raise ValueError("invalid_people_role")
            cleaned.append(
                {
                    "name": str(row.get("name") or ""),
                    "email": str(row.get("email") or ""),
                    "role": role,
                }
            )
        settings["people"] = cleaned

    onboarding = _onboarding(settings)
    if patch.get("carriers") is not None:
        carriers = patch["carriers"]
        if not isinstance(carriers, list):
            raise ValueError("invalid_carriers")
        onboarding["carriers"] = [str(c).strip() for c in carriers if str(c).strip()]
    if patch.get("tolerances") is not None:
        raw = patch["tolerances"]
        if not isinstance(raw, dict):
            raise ValueError("invalid_tolerances")
        try:
            absolute = int(raw.get("absolute_minor", DEFAULT_ABSOLUTE_TOLERANCE_MINOR))
            percent = float(raw.get("percent", DEFAULT_PERCENT_TOLERANCE))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_tolerances") from exc
        onboarding["tolerances"] = {"absolute_minor": absolute, "percent": percent}
    settings["client_onboarding"] = onboarding
    org.settings_json = settings
    flag_modified(org, "settings_json")
    return org
