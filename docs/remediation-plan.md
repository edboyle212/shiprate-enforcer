# Remediation plan — Shiprate Enforcer

Evidence gathered from `main` on 2026-09-27. Application code was not changed in this task.

## Measured baseline (2026-09-27)

| Check | Command / setup | Result |
| --- | --- | --- |
| Pytest (prompt default) | `cd apps/api && PYTHONPATH=. python -m pytest tests -q -rs` | **Fails:** `python: command not found` on this machine |
| Pytest (repo venv, no DB URL) | `apps/api/.venv/bin/python -m pytest tests -q -rs` | **102 passed, 5 skipped** — all skips: `DATABASE_URL / TEST_DATABASE_URL not set` |
| Pytest (test DB + RLS flag) | `TEST_DATABASE_URL=postgresql://shiprate:shiprate@localhost:5432/shiprate_test`, `SHIPRATE_RLS_ENABLED=1`, same venv | **106 passed, 1 skipped** (`test_rls_policy_documented_when_skipped` — intentional meta test when RLS is on) |
| Former “DB skip” tests | Same env; files `test_compliance`, `test_import_idempotency`, `test_matching`, `test_rate_card_immutability`, `test_tenant_isolation` | **10 passed, 1 skipped**; `test_org_b_cannot_read_org_a_shipment` **PASSED** |
| Coverage | `python3 -m pytest tests -q --cov=app --cov-report=term` with test DB + RLS | **86.34%** total (gate 85%); still dominated by `AsyncMock` router tests |
| Playwright | `cd apps/web && pnpm exec playwright test` (starts `pnpm dev` via `webServer`) | **9 passed** in ~6.1s; **no API or Postgres** in the loop |
| Local Postgres | `localhost:5432`, dev DB `shiprate` untouched; `shiprate_test` created and migrated to `006_negotiation` | Role `shiprate`: not superuser; owns tables. RLS: `organizations` enabled not forced; `etl_processed_objects`, `users`, `wms_partners` no RLS |
| Web versions | `apps/web/package.json`, installed `next` | **next 15.1.0**, React **19.3.0** |

## 1. Summary

- **Current:** Callers impersonate any tenant via `X-Organization-Id`; platform admin is a header; partner routes are open; RLS fails open when tenant context is unset; tenants can post carrier replies and record credits; rating defaults to zero or zone 8 instead of failing; CI pytest never required a database; Playwright only checks that pages return HTTP &lt; 500.
- **Target:** Verified auth (Clerk JWT + DB roles), fail-closed RLS on a non-owner `shiprate_app` role, one versioned rating engine with real replay, line-level matching and component compliance, disputes via outbox with platform-controlled credits and carrier channels.
- **Go/no-go for client onboarding (report-only, no carrier mail):** Phases **0, 1, and 2** exit criteria green in CI with **0 test skips**, pytest on real Postgres as `shiprate_app`, Playwright against live API + DB.
- **Go/no-go for outbound carrier contact:** Phase **3** green plus Edward sign-off on **D3** (channel per carrier).
- **Until then:** `OUTBOUND_CARRIER_SEND_ENABLED=false` (Phase 0); no production carrier email.

## 2. Findings register

| ID | Status | Evidence (`file:line`) | Severity | Fix phase |
| --- | --- | --- | --- | --- |
| P0-1 | CONFIRMED | `app/middleware/tenancy.py:19-24`, `:26-33`; `app/config.py:38`; `apps/web/lib/session.ts:9`, `apps/web/lib/api.ts:12` | P0 | 0 |
| P0-2 | CONFIRMED | `app/routers/orgs.py:193-196` | P0 | 0 |
| P0-3 | CONFIRMED | `app/routers/partners.py:36-38,41-50,88-103,106-129,132-155`; `app/routers/imports.py:402-424`; `partners.py:138-141` | P0 | 0 |
| P0-4 | CONFIRMED | `alembic/versions/001_initial_schema_rls.py:209,220,224`; `003_compliance_matching.py:181,185`; `004_disputes_ai_reporting.py:249,253`; `006_negotiation.py:103,107`; `002_wms_partners_etl.py:34-53`; `005_force_rls.py:17-19`; `001:206-210`; `docker-compose.yml:5` | P0 | 0 |
| P0-5 | CONFIRMED | `app/routers/disputes.py:292-321,368-387`; `app/services/negotiation.py:258-259,415-438`; `app/routers/orgs.py:149-150`; `app/services/org_settings.py:13` | P0 | 0 |
| P0-6 | CONFIRMED | `app/services/org_settings.py:38,43`; `app/services/negotiation.py:246-249,379-382`; `app/services/compliance.py:147-156`; `app/rating/engine.py:69-83` | P0 | 0 |
| P0-7 | CONFIRMED | `apps/web/package.json:12` — Next **15.1.0**; CVE-2025-55182 (fix 15.1.9+), CVE-2025-55183/55184 (15.1.11+), CVE-2025-29927 (15.2.3+ only on 15.x line) | P0 | 0 |
| P1-1 | CONFIRMED | `app/rating/engine.py:41,56,59` | P1 | 1 |
| P1-2 | CONFIRMED | `app/rating/engine.py:14,28,32-41,55,65-67`; `app/routers/imports.py:152-157,203` | P1 | 1 |
| P1-3 | CONFIRMED | `app/services/matching.py:205,212,223`; `app/services/compliance.py:386` | P1 | 2 |
| P1-4 | CONFIRMED | `app/services/compliance.py:331-346,370-373`; `app/routers/imports.py:204-212` | P1 | 1 / 2 |
| P1-5 | CONFIRMED | `apps/api/rating_engine/engine.py:34,38`; `app/rating/engine.py:74,97-104` | P1 | 1 |
| P1-6 | CONFIRMED | `app/services/compliance.py:173-187,231-248`; `app/services/matching.py:88-106`; `app/services/rate_cards.py:64-74`; `app/db/tenant.py` (test helper in app package) | P1 | 2 |
| P1-7 | CONFIRMED | `app/routers/imports.py:248-253`; `app/routers/rating.py:58,70-71`; `app/services/reporting.py:31-36`; `app/services/disputes.py:25-26` | P1 | 1 |
| P1-8 | CONFIRMED | `app/services/compliance.py:120-129` | P1 | 2 |
| P1-9 | CONFIRMED | `app/services/negotiation.py:208-209,383`; `app/routers/disputes.py:287,343`; `app/services/mail.py:77-94` | P1 | 3 |
| P1-10 | CONFIRMED | `app/services/mail.py:50-61,101,115`; `app/services/negotiation.py:155` | P1 | 0 / 3 |
| P1-11 | CONFIRMED | `app/services/mail.py:86`; `app/services/storage.py:41,49-51,75-78`; `app/routers/imports.py:65` | P1 | 3 |
| P1-12 | CONFIRMED | `app/services/negotiation.py:370-383,425-427,132-134` | P1 | 3 |
| P1-13 | CONFIRMED | Product — `docs/client-setup.md:54` assumes email; no channel model | P1 | 3 (D3) |
| P2-1 | CONFIRMED | `app/routers/imports.py:61,65,67,160-163` | P2 | 4 |
| P2-2 | CONFIRMED | `app/routers/etl.py:14-15,39`; `app/services/storage.py:60,68` | P2 | 0 / 4 |
| P2-3 | CONFIRMED | `app/routers/imports.py:313-316,353-378`; no DB immutability trigger in migrations | P2 | 0 / 1 / 4 |
| P2-4 | CONFIRMED | `app/services/ai_mapping.py:37-50` | P2 | 4 |
| P2-5 | CONFIRMED | `apps/api/pyproject.toml` (minimum-only pins); `rate_cards.py:22`; `apps/web/package-lock.json` + `pnpm-lock.yaml` | P2 | 0 / 4 |
| P2-6 | CONFIRMED | `app/services/compliance.py:369-381` | P2 | 4 |
| T-1 | CONFIRMED | `.github/workflows/ci.yml` — no Postgres `services:`; 5 skips without `TEST_DATABASE_URL` | Test | 0 |
| T-2 | CONFIRMED | `apps/api/tests/conftest.py:22-37` (`AsyncMock` session); 86.34% coverage with DB env but mocks still dominate | Test | 0 |
| T-3 | CONFIRMED | `conftest.py:72-75`; `test_tenant_isolation.py:30-31,62-68` | Test | 0 |
| T-4 | CONFIRMED | `.github/workflows/ci.yml:40,43` | Test | 0 |
| NEW-1 | CONFIRMED | `app/routers/orgs.py:84-100`; `app/routers/partners.py:106-129` | P0 | 0 |
| NEW-2 | CONFIRMED | `app/routers/orgs.py:151-152`; `app/services/org_settings.py:54-58` | P0 | 0 |
| NEW-3 | CONFIRMED | `app/services/compliance.py:132-144`; `app/rating/engine.py:41`; defaults GND / 1 oz / empty dest | P0 | 0 block / 1 fix |
| NEW-4 | CONFIRMED | `app/services/matching.py:174-176`; `app/services/compliance.py:359-362`; `apps/web/lib/api.ts:505` | P1 | 2 |
| NEW-5 | CONFIRMED | `app/routers/rating.py:62` | P2 | 1 |
| NEW-6 | CONFIRMED | `app/routers/imports.py:447-481`; `app/services/compliance.py:77-78` | P2 | 1 |
| NEW-7 | CONFIRMED | `apps/web/e2e/*.spec.ts`; `playwright.config.ts:4-5`; CI web job — no API | Test | 0 |
| NEW-8 | CONFIRMED | Untracked `apps/api/data/uploads/...` in git status | P2 | 0 |
| NEW-9 | CONFIRMED | `app/main.py:12`; `app/config.py:42-43` | P2 | 4 |

**Counts:** **30** confirmed (adversarial review IDs), **0** rejected, **9** new (`NEW-*` / extra test rows) → **39** total finding IDs in this register.

## 3. Decisions needed from Edward

### D1 — Auth provider and role model

| Option | Notes |
| --- | --- |
| Clerk | Already stubbed in API; org in JWT; fastest path |
| Auth0 / WorkOS | More enterprise IAM; more integration work |

**Recommendation:** Clerk — JWKS verification, org claim from token, roles in our DB: `tenant_owner`, `tenant_admin`, `tenant_member`, `tenant_viewer`, `partner_admin`, `partner_viewer`, `platform_admin`.

**Blocks:** Phase 0 auth, Playwright auth fixtures.

### D2 — Carriers and services (v1)

**Recommendation:** UPS + FedEx, US domestic, Ground + 2Day + Next Day Air; accessorials: residential, DAS, AHS only.

**Blocks:** Phase 1 golden cases. Need **≥20 anonymized invoice lines per service** with known correct amounts.

### D3 — Dispute channel per carrier

| Option | Notes |
| --- | --- |
| Email | Current docs assume this; unverified |
| Portal + human filing | Evidence packet (PDF/CSV), deadline tracking |
| Carrier API | Auth and windows vary |

**Recommendation:** Portal packet + human filing in v1; email only with written carrier confirmation.

**Blocks:** Phase 3 adapters and outbound go-live.

### D4 — Who may record credits

**Recommendation:** `platform_admin` only; carrier credit document attached (`source_file_id` + reference); dual approval over a threshold.

**Blocks:** Phase 0 lockdown, Phase 3 ledger.

### D5 — Who approves rate cards

**Recommendation:** `platform_admin` after tenant uploads contract (tenant cannot self-approve).

**Blocks:** P2-3, Phase 0.

## 4. Test foundation (every phase)

- **Postgres 16** in CI (`services:`). Local: **`shiprate_test`** only — never point tests at dev DB `shiprate`.
- **Roles:** `shiprate_migrator` (owns schema, runs Alembic); `shiprate_app` (`NOSUPERUSER`, `NOBYPASSRLS`, not owner, DML only). **App and pytest use `shiprate_app`.**
- **pytest:** Session fixture migrates to head; per-test transaction rollback; `httpx.AsyncClient` against real app+DB; delete `skip_until_implemented` and `AsyncMock` DB tests; missing `TEST_DATABASE_URL` **fails** the run; `conftest` hook fails on any skip; coverage only from DB-backed runs.
- **Playwright:** CI order: Postgres → migrate → `apps/api/scripts/seed_e2e.py` → `uvicorn` → `next build && next start` → `playwright test`; Clerk test tokens; mail capture sink; flow specs replace page-load-only tests.
- **CI:** Lint blocking; `pnpm audit --audit-level=high`.

## 5. Phases

### Phase 0 — Stop the bleeding

**Scope:** P0-1–P0-7, NEW-1, NEW-2, NEW-3 (block), NEW-7, NEW-8, T-1–T-4, P1-10 (fail not fake send), P2-2 (org binding), P2-3 (approval role), P2-5 (lockfile).

| PR | Work | Primary files |
| --- | --- | --- |
| 0.1 | DB test harness, CI Postgres, delete mock router coverage tests | `.github/workflows/ci.yml`, `tests/conftest.py`, `tests/db.py`, `scripts/create_roles.sql`, `docker-compose.yml` |
| 0.2 | Clerk JWT; dev header only `ENV=local` + `ALLOW_DEV_TENANT_HEADER=1` | `app/auth/`, `app/middleware/tenancy.py`, `app/config.py`, `apps/web` Clerk |
| 0.3 | Roles, `platform_admins`, remove `X-Platform-Admin`, lock `POST /organizations` | `app/routers/orgs.py`, routers deps |
| 0.4 | Partner memberships, FK `organizations.partner_id`, secure partner + ETL routes | `app/routers/partners.py`, `imports.py`, `etl.py` |
| 0.5 | Fail-closed RLS migration `007` | `alembic/versions/007_*.py` |
| 0.6 | Platform-only replies/credits/autonomy; remove auto-credit; outbound flag | `negotiation.py`, `disputes.py`, `mail.py` |
| 0.7 | `carrier_contacts`; `discrepancies.carrier_code` | migration `009`, `org_settings.py` |
| 0.8 | Unrated guard — no discrepancy without rate | `compliance.py` |
| 0.9 | Next ≥15.2.3 (target 15.5.x patched), one lockfile, pin Python, gitignore uploads | `apps/web`, `pyproject.toml` |
| 0.10 | Full-stack Playwright CI job | `ci.yml`, `e2e/`, `scripts/seed_e2e.py` |

**Schema:** `007_fail_closed_rls`, `008_roles_partners`, `009_carrier_contacts` — each with tested `downgrade()`; 007 rollback documented as manual ops step.

**pytest (as `shiprate_app`):** `test_app_role_is_not_superuser_owner_or_bypassrls`, `test_every_org_table_has_forced_rls`, `test_no_tenant_context_sees_zero_rows`, `test_cross_tenant_insert_rejected`, `test_org_b_cannot_read_org_a_shipment`, auth 401/403 suite, platform/partner/money/carrier tests listed in planning notes, `test_etl_poll_uses_org_partner_not_body`.

**Playwright:** `auth.spec.ts`, `tenant-isolation.spec.ts`, `partner-scope.spec.ts`, `import-to-discrepancy.spec.ts`, `dispute-no-send.spec.ts`.

**Exit criteria:** CI **0 skips**; pytest as `shiprate_app`; Playwright with API+DB; audit clean; staging rejects `X-Organization-Id` without JWT.

**Risks:** Clerk vs 3PL hierarchy; org bootstrap vs forced RLS; coverage dip when removing mocks (do not lower gate).

**Estimate:** **20 engineer-days** (medium confidence): 0.1→3, 0.2→3, 0.3→2, 0.4→2, 0.5→2.5, 0.6→1.5, 0.7→1.5, 0.8→1, 0.9→1.5, 0.10→2.

---

### Phase 1 — Truthful rating

**Scope:** P1-1, P1-2, P1-4 (dating), P1-5, P1-7, P2-3 (schema), NEW-3 (fix), NEW-5, NEW-6.

Work items **1.1–1.12:** single engine; Pydantic `rules_json` + `rules_sha256`; fail-closed `Unrated`; origin/dest zones; lb rounding DIM; `shipment_packages`; `fuel_surcharge_index`; accessorials (D2); effective dating; Decimal money + `currencies`; real replay; import + strict rating request.

**Schema:** `010_rating_inputs`, `011_rate_card_dating`, `012_fuel_currency`.

**Tests:** `tests/golden/{carrier}/{service}/*.json` — `test_golden_case[case]`; unrated/dim/fuel/date/replay/currency tests; Hypothesis `test_rate_is_deterministic`; Playwright `rate-card-upload.spec.ts`.

**Exit criteria:** All golden cases exact; no default-rate paths; `rating_engine/` removed.

**Estimate:** **28 engineer-days** (low–medium confidence — depends on D2 data).

---

### Phase 2 — Line-level matching and compliance

**Scope:** P1-3, P1-4 (re-rating), P1-6, P1-8, NEW-4.

Work items **2.1–2.6:** charge-line model; component compliance; cross-job matching; re-rate supersede; reason codes; remove fabrication (`compliance.py:173-287`, `matching.py:75-148`, `rate_cards.py`, `app/db/tenant.py`).

**Schema:** `013_charge_lines`.

**Tests:** multi-line, adjustment, cross-file scope, rerate, reason codes, `test_no_stub_rows_created_anywhere`; Playwright `discrepancy-detail.spec.ts`.

**Exit criteria:** Sample month replay matches human review 100%; `rg integration-stub` / `test-stub` clean in CI.

**Estimate:** **14 engineer-days** (medium).

---

### Phase 3 — Dispute integrity

**Scope:** P1-9–P1-13.

Work items **3.1–3.6:** outbox + idempotency; async I/O; state machine + DB trigger; counter content guard; D3 channel adapters; `credit_entries` ledger.

**Schema:** `014_outbox`, `015_case_transitions`, `016_credit_ledger`.

**Tests:** commit ordering, retry dedup, illegal transitions, ledger immutability; Playwright `dispute-send.spec.ts`, `credit-entry.spec.ts`.

**Exit criteria:** Chaos test — no duplicate sends; ops sign-off on D3.

**Estimate:** **17 engineer-days** (medium).

---

### Phase 4 — Hardening

**Scope:** P2-1, P2-2 (path), P2-3 (trigger), P2-4, P2-5 (rest), P2-6, NEW-9.

Upload limits, path safety, immutability triggers, AI provider or gated stub, batch compliance queries, env-only CORS/S3.

**Tests:** upload limits, traversal, trigger block, query count; Playwright `upload-limits.spec.ts`.

**Exit criteria:** 100k-line load SLO; security review pass.

**Estimate:** **8 engineer-days** (medium–high).

## 6. Dependency graph

```mermaid
flowchart TD
  T01["0.1 DB test harness"] --> A02["0.2 Clerk JWT"]
  T01 --> R05["0.5 Fail-closed RLS"]
  T01 --> PW["0.10 Full-stack Playwright"]
  A02 --> R03["0.3 Roles and admin"]
  R03 --> P04["0.4 Partner auth"]
  R03 --> M06["0.6 Money lockdown"]
  R05 --> P04
  M06 --> C07["0.7 Carrier recipients"]
  T01 --> G08["0.8 Claim guard"]
  A02 --> PW
  G08 --> E13["1.3 Fail-closed engine"]
  E11["1.1 One engine"] --> E13
  S12["1.2 Rules schema"] --> E13
  E13 --> Z["1.4-1.8 Zones weight fuel accessorials"]
  Z --> D19["1.9 Effective dating"]
  D19 --> RP["1.11 Replay"]
  M110["1.10 Money parsing"] --> L21["2.1 Charge lines"]
  RP --> L21
  L21 --> C22["2.2 Component compliance"]
  C22 --> RR["2.4 Re-rating"]
  C22 --> RC["2.5 Reason codes"]
  C07 --> OB["3.1 Outbox"]
  RC --> OB
  OB --> SM["3.3 State machine"]
  SM --> LG["3.6 Credit ledger"]
  SM --> CH["3.5 Channel adapters"]
```

Parallel examples: **0.9** (Next/lockfile) with **1.10** (money parsing).

## 7. What we will not do in v1

- AI setting money, rates, reason codes, or dispute outcomes (beyond optional column mapping).
- Carriers/services outside **D2**; international, LTL, freight.
- FX conversion — report per currency separately.
- Automatic credits without platform-verified documents.
- **Autonomous** outbound negotiation tier until post-v1.
- Automated carrier API filing unless **D3** requires it for a carrier.
- White-label custom domains and partner embed iframes.

## Constraints (from review)

- Postgres remains system of record; money in integer minor units + `currency_code`.
- Rating engine deterministic and versioned; replay from stored inputs, card version, engine version.
- AI never sets money, rate tables, or dispute decisions.
- Fail closed on unrated inputs — never create a claim from a default.
- No credit or fee from tenant-controlled input.
- Each phase leaves `main` deployable, CI green, real tests not skips.
