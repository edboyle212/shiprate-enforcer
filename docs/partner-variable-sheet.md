# WMS partner variable sheet

Per-partner configuration. **Northstar WMS** (`northstar`) is the anonymized demo row; production partners follow the same schema.

| Variable | Type | Demo default (`northstar`) | Notes |
|----------|------|----------------------------|--------|
| `partner_id` | string | `northstar` | Stable slug |
| `ingest_mode` | enum | `file_drop` | `file_drop` \| `api` \| `manual` |
| `auth_model` | enum | TBD | OAuth, API key, SFTP, S3 IAM, none |
| `tenant_mapping` | map | TBD | `partner_tenant_id` → `organization_id` |
| `is_3pl` | bool? | null | One WMS tenant → many bill-to accounts |
| `export_methods` | string[] | `ad_hoc_csv` | api, scheduled_report, ad_hoc_csv, varies_by_warehouse |
| `export_fields` | object | {} | tracking, billed_weight, … null = unknown |
| `carriers_billed` | string[] | `UPS` | UPS, FedEx, … not hardware vendors |
| `embed_mode` | enum | `companion_url_only` | iframe, smarttask, marketplace, unknown |
| `ingest_mode_poc` | enum | `partner_uploads_client_data` | vs `client_self_upload` at rollout |
| `branding_mode` | enum | TBD | co_brand \| white_label |
| `commercial` | object | TBD | rev-share, billing party, DPA |

Stored in `wms_partners.profile_json` and `wms_partners.branding_json` via `PUT /api/v1/partners/{partner_id}/profile`.

Public co-brand fields (no auth): `GET /api/v1/partners/{partner_id}/public-branding` — `display_name`, `logo_url`, `primary_color` (demo seed uses `#0f766e`).
