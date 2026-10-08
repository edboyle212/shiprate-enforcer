"""Shared Northstar WMS demo identifiers (no partner-specific branding in filenames)."""

from __future__ import annotations

import uuid

PARTNER_ID = "northstar"
PARTNER_DISPLAY_NAME = "Northstar WMS"

DEMO_ORG_ID = uuid.UUID("01950000-0000-7000-8000-000000000010")
DEMO_ORG_NAME = "Northstar Demo Warehouse"
DEMO_ORG_SLUG = "northstar-demo-warehouse"

DEMO_RATE_CARD_ID = uuid.UUID("01950000-0000-7000-8000-000000000030")
DEMO_RATE_CARD_LABEL = "northstar-demo-gnd-v1"

# Deterministic rating snapshot (golden contract): allowed $5.00 on GND 4oz → zone 2.
DEMO_RATE_CARD_RULES: dict = {
    "zones": {"10001": 2},
    "weight_break_table_minor": {"GND|2|4oz": 450},
    "minimum_charge_minor": {"GND": 500},
}

DEMO_TRACKING = "1ZNORTH0000000001"
# Billed $15.00 vs allowed $5.00 + $5.00 tolerance → discrepancy.
DEMO_INVOICE_BILLED_MAJOR = "15.00"
