# Northstar WMS file-drop demo walkthrough

Anonymized partner demo for warehouse operators and WMS integrators. Partner slug: **northstar** (`Northstar WMS`).

## Prerequisites (Homebrew Postgres, no Docker)

1. **PostgreSQL** running locally with database `shiprate` (or set `DATABASE_URL`).

   ```bash
   brew services start postgresql@16
   createdb shiprate 2>/dev/null || true
   ```

   Default connection used by the API:

   `postgresql://shiprate:shiprate@localhost:5432/shiprate`

   Create role/database if needed (adjust to your local setup).

2. **API dependencies** (once per machine):

   ```bash
   cd apps/api
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   alembic upgrade head
   ```

3. **Web** (once per machine):

   ```bash
   cd apps/web
   npm install
   ```

## Start the stack

Terminal 1 — API:

```bash
cd apps/api
source .venv/bin/activate
export ALLOW_DEV_TENANT_HEADER=1
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — Web:

```bash
cd apps/web
npm run dev
```

Web: [http://127.0.0.1:43123](http://127.0.0.1:43123)  
API: [http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1)

## One command: seed + file drop + match + compliance

From the repository root (with `DATABASE_URL` set and API **stopped** or using a separate DB session — the script talks to Postgres directly):

```bash
chmod +x scripts/run-northstar-demo-drop.sh
./scripts/run-northstar-demo-drop.sh
```

This:

1. Seeds partner `northstar`, warehouse org, and an **approved** UPS rate card.
2. Copies `demo/fixtures/sample-shipments.csv` and `demo/fixtures/sample-invoice.csv` into the local ETL drop tree.
3. Runs the same steps as `POST /api/v1/etl/poll-drop`, maps CSV rows, runs matching, and compliance.

**Demo organization id** (paste into Account or browser `localStorage` key `shiprate_demo_org_id`):

`01950000-0000-7000-8000-000000000010`

**API tenancy header** (if calling REST directly):

`X-Organization-Id: 01950000-0000-7000-8000-000000000010`

Expected outcome: **one discrepancy** — invoice line billed **$15.00** vs allowed **$5.00** (deterministic rating), over default tolerance.

## View results in the UI

1. Open [http://127.0.0.1:43123/account](http://127.0.0.1:43123/account) and paste the organization id above (saved in the browser).
2. Open [http://127.0.0.1:43123/discrepancies](http://127.0.0.1:43123/discrepancies) — you should see the overcharge row.
3. Optional: [http://127.0.0.1:43123/dashboard](http://127.0.0.1:43123/dashboard) for KPIs.
4. Partner surfaces: `/partner/northstar/onboarding`, `/p/northstar/onboarding`.

Dispute drafts remain **draft-only** in this demo; nothing is sent to carriers.

## Fixtures

| File | Role |
|------|------|
| `demo/fixtures/sample-shipments.csv` | Warehouse shipment export |
| `demo/fixtures/sample-invoice.csv` | Carrier invoice line with intentional overcharge |

ETL layout (local filesystem mirror):

`data/uploads/etl-drops/northstar/{organization_id}/shipments|invoices/…`

## Re-run

Each run stages timestamped files under the drop folder so `poll-drop` ingests new objects. Re-run:

```bash
./scripts/run-northstar-demo-drop.sh --skip-seed
```

after the first seed.

## HTTP alternative (API running)

With the API up and org header set:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/etl/poll-drop \
  -H "X-Organization-Id: 01950000-0000-7000-8000-000000000010"
```

Then process pending jobs via the one-shot script’s import/match steps, or use Import center + **Run sample CSV pipeline** (requires the seeded rate card).
