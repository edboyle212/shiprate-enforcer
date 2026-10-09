# Shiprate Enforcer

Multi-tenant parcel rate-compliance SaaS. PostgreSQL is the system of record; a versioned Python rating engine computes allowed amounts in **minor units** (BIGINT cents + `currency_code`).

## Local stack

### 1. Database and object storage

```bash
docker compose up -d
```

- Postgres 16 → `postgresql://shiprate:shiprate@localhost:5432/shiprate`
- MinIO → `http://localhost:9000` (bucket `shiprate-uploads`, keys `minioadmin` / `minioadmin`)

### 2. API (FastAPI)

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Dev tenancy: send header `X-Organization-Id: <organization-uuid>` (create one via `POST /api/v1/organizations`).

RLS details: [apps/api/docs/rls-set-local.md](apps/api/docs/rls-set-local.md)

### 3. Web (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

Dev server listens on [http://127.0.0.1:43123](http://127.0.0.1:43123).

Routes:

- Dashboard: `/dashboard`
- Account profile: `/account`
- Import center: `/imports`
- Discrepancies: `/discrepancies` (detail: `/discrepancies/{id}`)
- Partner wizard: `/partner/{partnerId}/onboarding`
- Partner accounts: `/partner/{partnerId}/accounts`
- Client wizard: `/p/{partnerSlug}/onboarding`

**Demo (white-label):** seed Northstar WMS with `python apps/api/scripts/seed_demo_northstar.py`, then open `/p/northstar/onboarding` or run `scripts/run-northstar-demo-drop.sh`. Partner branding is served from `GET /api/v1/partners/northstar/public-branding`.

Dispute mail is gated by the org **autonomy tier** (`draft`, `approve_each`, `autonomous`). Recovered credits record a platform fee (`recovery_fee_bps`). AI column mapping is assist-only (`SHIPRATE_AI_ENABLED=1` + provider keys); it never writes rate tables or monetary dispute decisions.

### API highlights (prefix `/api/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/imports/map-csv` | Map shipment export CSV → `shipments` |
| POST | `/imports/map-invoice-csv` | Map carrier invoice CSV → `carrier_invoice_lines` |
| POST | `/matching/run` | Tracking match (exact → normalized); optional compliance |
| POST | `/matching/manual-link` | Manual shipment ↔ invoice line link |
| POST | `/compliance/run` | Rate matched pairs vs approved rate card |
| GET | `/discrepancies` | List over-tolerance rows |
| GET | `/discrepancies/{id}` | Detail with rating trace summary |
| PATCH | `/discrepancies/{id}` | Review workflow (status + comment) |
| POST | `/discrepancies/{id}/open-case` | Open dispute case (claim from variance) |
| GET | `/dispute-cases` | List dispute cases |
| GET | `/dispute-cases/{id}` | Case detail, drafts, events |
| POST | `/dispute-cases/{id}/draft` | Generate email draft from trace |
| POST | `/dispute-cases/{id}/approve-draft` | Human approve draft (no send) |
| POST | `/dispute-cases/{id}/negotiate` | One agent step (draft or send by tier) |
| POST | `/dispute-cases/{id}/replies` | Post a carrier reply |
| POST | `/dispute-cases/{id}/approve-send` | Send after approve (`approve_each`) |
| POST | `/dispute-cases/{id}/stop` | Stop the case |
| POST | `/dispute-cases/{id}/record-credit` | Platform records recovered amount + fee |
| PATCH | `/organizations/current` | Client sets autonomy tier (not fee) |
| GET/PATCH | `/organizations/current/profile` | Client account profile |
| GET/POST | `/partners/{partner_id}/accounts` | Publisher client account list and create |
| GET | `/partners/{partner_id}/accounts/{org_id}` | Publisher account profile + KPIs |
| GET | `/reporting/summary` | Dashboard KPIs |
| POST | `/ai/map-columns` | Proposed CSV column mapping (template or AI) |

Dev tenancy header: `X-Organization-Id`.

Dispute email (Resend), recovery fees, and operator steps: [docs/app-setup.md](docs/app-setup.md). Client onboarding: [docs/client-setup.md](docs/client-setup.md).

## Tests

See [docs/testing.md](docs/testing.md).

```bash
cd apps/api && PYTHONPATH=. python3 -m pytest tests -v
```

Integration tests (import idempotency, rate-card immutability, RLS) need `DATABASE_URL` and migrations; RLS isolation also requires `SHIPRATE_RLS_ENABLED=1`.

## Product docs

- [App setup](docs/app-setup.md) — local stack, Resend, platform fees, operator checklist
- [Client setup](docs/client-setup.md) — client onboarding, account profile, disputes
- [MVP specification](docs/shiprate-mvp-spec.md)
- [Partner variable sheet](docs/partner-variable-sheet.md)
- [ETL drop contract](docs/etl-drop-contract.md)
- [Wizard field lists](docs/wizard-field-lists.md)

## Monorepo layout

| Path | Purpose |
|------|---------|
| `apps/api` | FastAPI, SQLAlchemy, Alembic, `app.rating.engine` |
| `apps/web` | Next.js App Router UI shells |
| `docker-compose.yml` | Postgres + MinIO |
