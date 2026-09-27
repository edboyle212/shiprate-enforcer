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

- Partner wizard: `/partner/{partnerId}/onboarding`
- Client wizard: `/p/{partnerSlug}/onboarding`

## Tests

See [docs/testing.md](docs/testing.md).

```bash
cd apps/api && PYTHONPATH=. python3 -m pytest tests -v
```

Integration tests (import idempotency, rate-card immutability, RLS) need `DATABASE_URL` and migrations; RLS isolation also requires `SHIPRATE_RLS_ENABLED=1`.

## Monorepo layout

| Path | Purpose |
|------|---------|
| `apps/api` | FastAPI, SQLAlchemy, Alembic, `app.rating.engine` |
| `apps/web` | Next.js App Router UI shells |
| `docker-compose.yml` | Postgres + MinIO |
