# Testing

How to run Shiprate Enforcer tests locally and in CI.

## Prerequisites

- Python 3.12+ for API tests
- Node 20+ and pnpm for web e2e (once `apps/web` is scaffolded)

## API (pytest)

From the repository root:

```bash
cd apps/api
python -m pip install pytest pytest-asyncio httpx
PYTHONPATH=. pytest tests -v
```

Or from repo root in one line:

```bash
PYTHONPATH=apps/api pytest apps/api/tests -v
```

### What the suite enforces

| Test file | Plan gate |
|-----------|-----------|
| `test_tenant_isolation.py` | Org B cannot read org A rows (RLS). Skips until `SHIPRATE_RLS_ENABLED=1` and DB helpers exist. |
| `test_import_idempotency.py` | Same `idempotency_key` does not duplicate `import_jobs`. Skips until DB + service implemented. |
| `test_rate_card_immutability.py` | Approved `rate_card_version` cannot be mutated in place. |
| `test_rating_golden.py` | Golden fixture → allowed total + trace includes `engine_version`. |
| `test_rating_replay.py` | Same inputs + `rule_bundle_hash` → identical result. |
| `test_matching.py` | Normalized tracking match; no match when either side missing. Integration: persisted shipment↔invoice link (skips without DB). |
| `test_compliance.py` | Billed above allowed + absolute tolerance → discrepancy with reason code. Integration: persisted discrepancy row (skips without DB). |
| `test_dispute_draft.py` | Dispute draft cites trace facts; draft-only (not sent). |
| `test_negotiation.py` | Tiers (`draft` never sends, `approve_each` after approve, `autonomous` sends), platform pause, fee math. |
| `test_ai_mapping.py` | Template mapping when AI disabled; `ai_runtime_enabled` gate on env + API keys. |
| `test_ai_mapping_stub.py` | `map_columns` with stub client writes `ai_decision_requests` / `ai_decision_results`. |
| `test_org_profile.py` | Profile GET/PATCH updates name, tolerances, autonomy; recovery fee stays platform-set. |
| `test_partner_accounts.py` | Partner account list is scoped to that partner; detail 404s for another partner's org. |
| `test_reporting_summary.py` | `GET /reporting/summary` returns dashboard KPI keys (`discrepancy_count`, `total_overcharge_minor`, `open_disputes`, `recovered_total_minor`, `fee_total_minor`, `import_job_count`, `compliance_rate`, `compliance_rate_note`). |

Golden fixtures live in `apps/api/tests/fixtures/`:

- `golden_rating_request.json` — GND parcel, zone from dest ZIP, minimum charge floor
- `golden_rating_expected.json` — expected allowed total (500 USD minor units) and trace fields

### Integration / RLS

Set `DATABASE_URL` or `TEST_DATABASE_URL` for database-backed tests. Tenant isolation tests additionally require `SHIPRATE_RLS_ENABLED=1` once RLS is merged.

Expected import paths (Building Agent contract — first match wins):

- DB tenant: `app.db.tenant`, `app.database.tenant`, `shiprate.db.tenant`
- Import jobs: `app.services.import_jobs`, `app.imports.jobs`
- Rate cards: `app.services.rate_cards`, `app.contracts.rate_cards`
- Rating engine: `app.rating.engine`, `app.engine.rating`, `shiprate.rating.engine`
- Tracking match: `app.services.matching`, `app.matching.engine`, `shiprate.matching`
  - `normalize_tracking_number` / `normalize_tracking`
  - `match_invoice_line_to_shipment` / `tracking_numbers_match` / `match_by_tracking`
  - Integration: `persist_tracking_match` or `link_invoice_line_to_shipment` + lookup helper
- Compliance: `app.services.compliance`, `app.compliance.engine`, `shiprate.compliance`
  - `evaluate_compliance` / `check_line_compliance` — returns `None` when within tolerance
  - Over tolerance: `reason_code` in `BILLED_EXCEEDS_ALLOWED`, `OVER_TOLERANCE` (case variants OK)
  - Integration: `run_compliance_for_invoice_line` / `create_discrepancy_for_line` + list/get discrepancies

## Web (Playwright)

Once the Next.js app exists under `apps/web`:

```bash
cd apps/web
pnpm install
pnpm dev   # should listen on http://127.0.0.1:43123
pnpm exec playwright test
```

E2e specs:

- `apps/web/e2e/smoke.spec.ts` — home or onboarding loads.
- `apps/web/e2e/pages.spec.ts` — dashboard, imports, discrepancies, account, partner flows (sets demo org in `localStorage`).

API coverage gate: `pytest --cov=app --cov-fail-under=85` (see `apps/api/pyproject.toml`).

CI runs API pytest on every push/PR. The Playwright job runs only when `apps/web/package.json` is present; it does not start a dev server in CI yet (job may report soft failures until wired).

## Continuous integration

Workflow: `.github/workflows/ci.yml`

- **api-pytest** — `pytest apps/api/tests`
- **web-playwright** — conditional on web package; optional lint via ruff on API (continue-on-error)
