# ETL file-drop contract (POC)

Partner pushes files; Shiprate ingests through the **same pipeline** as browser upload.

## Layout (variables per partner)

Default prefix (S3 or local mirror):

```
{etl_drop_root}/{partner_id}/{organization_id}/shipments/{filename}
{etl_drop_root}/{partner_id}/{organization_id}/invoices/{filename}
{etl_drop_root}/{partner_id}/{organization_id}/rate_cards/{filename}
```

- **Transport:** S3-compatible (MinIO locally) or filesystem when `S3_ENDPOINT_URL` unset (`ETL_DROP_ROOT` env).
- **Cadence:** on-demand; call `POST /api/v1/etl/poll-drop` or run on schedule (Temporal later).
- **Idempotency:** `(organization_id, storage_key)` in `etl_processed_objects`; content also deduped by `(organization_id, sha256)` on `source_files`.
- **Format:** CSV/XLSX first; same mappers as manual import.
- **Tenancy:** path includes `organization_id` (UUID). Map from `partner_tenant_id` via org record or partner profile mapping table (TBD).
- **Failure:** import job `failed` + DQ issue (future); no silent partial rating.

## JASCI POC

JASCI collects client files and drops under `jasci/{org_uuid}/…`. No REST API required.
