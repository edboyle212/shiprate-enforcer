# UAT day-one checklist

Use this to confirm **local** matches **GitHub (`origin/main`)** before user acceptance testing.

## 1. Git sync (local ↔ cloud)

```bash
cd /path/to/shiprate-enforcer
git fetch origin
git status   # expect: "up to date with 'origin/main'"
git pull origin main
git log -1 --oneline
```

Compare that commit SHA with GitHub → **main** → latest commit. They must match.

Current feature baseline (as of last push):

- `75bd735` — API coverage gate (85%) + Playwright page e2e
- `3a040f0` — setup docs, README, negotiation Alembic `006_negotiation`

## 2. Database (negotiation tables)

After pull, on any environment running UAT:

```bash
cd apps/api
alembic upgrade head   # applies 006_negotiation if not already applied
```

## 3. Run stack locally (UAT against local)

See [app-setup.md](./app-setup.md) for full steps. Short version:

```bash
docker compose up -d
cd apps/api && uvicorn app.main:app --reload --port 8000
cd apps/web && pnpm dev   # http://127.0.0.1:43123
```

Set `X-Organization-Id` in the UI (Account page) or `localStorage` key `shiprate_demo_org_id`.

Optional dispute send: configure Resend in `apps/api/.env` (see app-setup § Dispute email).

## 4. Automated smoke (before testers arrive)

```bash
cd apps/api && PYTHONPATH=. python3 -m pytest tests -q --cov=app --cov-fail-under=85
cd apps/web && pnpm exec playwright test
```

## 5. Hosted “cloud” app (if you use Vercel / other)

Git sync does **not** auto-deploy. After `git pull` on your laptop, trigger a **production deploy** from the same commit SHA as `origin/main` (Vercel dashboard → Deployments → Redeploy, or push to the connected branch).

Set production env vars to match local: API URL for web (`NEXT_PUBLIC_API_URL`), Resend keys on API, `DATABASE_URL`, etc.

## 6. GitHub Actions note

If Actions shows “workflow file issue” with **0 jobs**, enable Actions for the repo (Settings → Actions) or check billing on private repos. Local pytest/Playwright above are the UAT gate until CI runs.

## 7. Client testers

Share [client-setup.md](./client-setup.md) for onboarding flows and org header behavior.
