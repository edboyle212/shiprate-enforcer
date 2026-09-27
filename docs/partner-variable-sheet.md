# WMS partner variable sheet

Per-partner configuration. **JASCI row is TBD** until the partner admin wizard is completed.

| Variable | Type | POC default | Notes |
|----------|------|-------------|--------|
| `partner_id` | string | `jasci` | Stable slug |
| `ingest_mode` | enum | `file_drop` | `file_drop` \| `api` \| `manual` |
| `auth_model` | enum | TBD | OAuth, API key, SFTP, S3 IAM, none |
| `tenant_mapping` | map | TBD | `partner_tenant_id` → `organization_id` |
| `is_3pl` | bool? | null | One WMS tenant → many bill-to accounts |
| `export_methods` | string[] | [] | api, scheduled_report, ad_hoc_csv, varies_by_warehouse |
| `export_fields` | object | {} | tracking, billed_weight, … null = unknown |
| `carriers_billed` | string[] | [] | UPS, FedEx, … not hardware vendors |
| `embed_mode` | enum | `companion_url_only` | iframe, smarttask, marketplace, unknown |
| `ingest_mode_poc` | enum | `partner_uploads_client_data` | vs `client_self_upload` at rollout |
| `branding_mode` | enum | TBD | co_brand \| white_label |
| `commercial` | object | TBD | rev-share, billing party, DPA |

Stored in `wms_partners.profile_json` and `wms_partners.branding_json` via `PUT /api/v1/partners/{partner_id}/profile`.
