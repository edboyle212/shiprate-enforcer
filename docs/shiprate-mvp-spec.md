# Shiprate Enforcer — MVP specification (Track A)

Durable summary aligned with the updated product plan. **Deterministic rating is source of truth;** AI (Jev → Grok → Claude) assists mapping only when flagged.

## Product shape

- Multi-tenant SaaS; RLS on tenant tables; money in minor units + ISO currency.
- **Free test:** CSV/XLSX upload → mapping confirm → rate → discrepancies (compliance slice next).
- **POC:** WMS partner drops client files via [ETL drop contract](./etl-drop-contract.md).
- **Rollout:** co-branded/white-label URL; client self-upload.

## Stack (MVP)

Next.js + FastAPI monolith, PostgreSQL, S3/MinIO, Clerk stub (`X-Organization-Id` dev), Temporal deferred.

## Implementation map

| Area | Location |
|------|----------|
| Tenancy / RLS | `apps/api/app/db`, Alembic `001` |
| Uploads | `POST /source-files`, `import-jobs` |
| Partner variables | [partner-variable-sheet.md](./partner-variable-sheet.md), `wms_partners` |
| Wizards | [wizard-field-lists.md](./wizard-field-lists.md), `apps/web/app/partner`, `apps/web/app/p` |
| ETL | [etl-drop-contract.md](./etl-drop-contract.md), `POST /etl/poll-drop` |
| Rating | `apps/api/rating_engine`, golden tests |
| Tests | [testing.md](./testing.md) |

## AI cascade (not in Track A code path yet)

Fingerprint → Jev → Grok → Claude → human accept. Never rates or submits disputes.

## Out of scope (Track B)

JASCI REST, SmartTask embed, custom domains, rev-share billing automation.
