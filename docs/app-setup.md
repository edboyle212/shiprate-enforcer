# App setup (platform / operator)

Steps to run Shiprate Enforcer locally or in a hosted environment, and to turn on **dispute email from your domain** (Resend) so carrier replies stay with you.

For what **clients** do after you invite them, see [client-setup.md](./client-setup.md).

---

## 1. Prerequisites

- Docker Desktop (or Docker) for Postgres and MinIO
- Python 3.12+
- Node 20+ and npm (web app)

---

## 2. Start infrastructure

From the repo root:

```bash
docker compose up -d
```

| Service | URL / connection |
|---------|----------------|
| Postgres 16 | `postgresql://shiprate:shiprate@localhost:5432/shiprate` |
| MinIO | `http://localhost:9000` — bucket `shiprate-uploads`, keys `minioadmin` / `minioadmin` |

---

## 3. API

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API base: `http://127.0.0.1:8000/api/v1`
- Interactive docs: `http://127.0.0.1:8000/docs`
- Dev tenancy: every request (except creating an org) needs header `X-Organization-Id: <uuid>`

Optional env file: `apps/api/.env` (see sections below).

RLS notes: [apps/api/docs/rls-set-local.md](../apps/api/docs/rls-set-local.md)

---

## 4. Web

```bash
cd apps/web
npm install
npm run dev
```

- UI: [http://127.0.0.1:43123](http://127.0.0.1:43123)
- API URL for the browser defaults to `http://127.0.0.1:8000/api/v1` (`NEXT_PUBLIC_API_URL` to override)

---

## 5. Smoke check

1. Open [http://127.0.0.1:43123/imports](http://127.0.0.1:43123/imports).
2. Create or paste an **Organization ID** (from `POST /api/v1/organizations` or the demo pipeline).
3. Click **Run sample CSV pipeline** (requires an approved rate card in the DB for that org).
4. Open [http://127.0.0.1:43123/discrepancies](http://127.0.0.1:43123/discrepancies) and confirm rows appear.

Tests: [testing.md](./testing.md).

---

## 6. Dispute email (Resend) — stay in the loop

Disputes should send **from your platform**, not from the client’s personal Gmail. The API uses [Resend](https://resend.com) when configured.

### 6.1 Resend dashboard

1. Add and **verify** your sending domain (DNS records Resend provides).
2. Create an **API key** with send permission.

### 6.2 API environment variables

Add to `apps/api/.env`:

| Variable | Required | Example |
|----------|----------|---------|
| `RESEND_API_KEY` | Yes | `re_...` |
| `DISPUTE_FROM_EMAIL` | Yes | `Shiprate Disputes <disputes@yourdomain.com>` |
| `DISPUTE_REPLY_TO` | No | `disputes@yourdomain.com` (defaults to same as From) |

Restart the API after changes.

### 6.3 Verify configuration

```bash
curl -s http://127.0.0.1:8000/api/v1/dispute-cases/outbound-mail \
  -H "X-Organization-Id: YOUR-ORG-UUID"
```

Expect: `{"configured":true,"from_address":"..."}`.

On the discrepancy detail page, the draft area should say email goes **from** your `from_address`.

### 6.4 What Send does

- **Send to carrier** calls `POST /dispute-cases/{id}/approve-send` with the draft message id.
- With Resend configured, the API POSTs to Resend; the draft banner is stripped from the body.
- Without Resend, sends are **log-only** (dev) — same button, no real delivery.

### 6.5 Inbound replies (later)

Carrier replies to your Resend inbox are **not** auto-ingested yet. Today you simulate replies with:

`POST /api/v1/dispute-cases/{case_id}/replies`

A future step is a Resend inbound webhook → that endpoint.

---

## 7. Per-client commercial settings (you set, not the client)

### Recovery fee (your % of recovered credits)

Basis points: `2000` = 20%. Snapshotted onto each dispute case at open time.

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/organizations/current/recovery-fee \
  -H "Content-Type: application/json" \
  -H "X-Organization-Id: CLIENT-ORG-UUID" \
  -H "X-Platform-Admin: 1" \
  -d '{"recovery_fee_bps": 2000}'
```

Clients cannot change `recovery_fee_bps` via profile or `PATCH /organizations/current`.

### Partner / publisher tools

- Partner profile: `GET/PUT /api/v1/partners/{partner_id}/profile`
- Client accounts list: `GET/POST /api/v1/partners/{partner_id}/accounts`
- Partner UI: `/partner/{partnerId}/onboarding`, `/partner/{partnerId}/accounts`

See [partner-variable-sheet.md](./partner-variable-sheet.md) and [wizard-field-lists.md](./wizard-field-lists.md).

---

## 8. Optional: AI column mapping

| Variable | Purpose |
|----------|---------|
| `SHIPRATE_AI_ENABLED=1` | Allow AI assist when provider keys exist |
| `AI_CLAUDE_API_KEY` / others | Provider keys in `apps/api/app/config.py` |

AI never sets rate tables or dispute claim amounts.

---

## 9. Production checklist (short)

- [ ] Postgres and object storage (S3 or MinIO) with backups
- [ ] `alembic upgrade head` on deploy
- [ ] `RESEND_API_KEY` + verified `DISPUTE_FROM_EMAIL`
- [ ] Clerk (or real auth) instead of header-only tenancy
- [ ] `recovery_fee_bps` set per client org before they open dispute cases
- [ ] Monitor Resend bounces / complaints

---

## Related docs

- [Client setup](./client-setup.md)
- [MVP spec](./shiprate-mvp-spec.md)
- [ETL drop contract](./etl-drop-contract.md)
