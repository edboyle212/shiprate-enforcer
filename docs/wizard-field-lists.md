# Onboarding wizard field lists

Demo partner slug: `northstar` (Northstar WMS). Client invite URLs use `/p/northstar/onboarding?org=`.

## Partner admin (`/partner/{partnerId}/onboarding`)

| Step | Fields |
|------|--------|
| Identity | `partner_name`, commercial contact (future), rev-share TBD |
| Branding | `branding_mode`, `display_name`, `logo_url`, `primary_color`, `support_email` |
| Export | `export_methods[]`, `export_notes` |
| Fields | `export_fields.{tracking,billed_weight,actual_weight,dims,service,carrier_account,ship_date,dest_postal,bill_to_client}` — null = unknown |
| Carriers | `carriers[]` |
| Embed | `embed_mode` |
| Ingest | `ingest_mode` — POC vs rollout |
| 3PL | `is_3pl` |
| Invite | `client_invite_base_url` — generated `/p/{partnerSlug}/onboarding?org=` |

API: `GET/PUT /api/v1/partners/{partner_id}/profile`

## Client warehouse (`/p/{partnerSlug}/onboarding`)

| Step | Fields |
|------|--------|
| Organization | name, slug (or token from invite) |
| Export overlay | override export method if `varies_by_warehouse` |
| Carriers | subset of partner tally |
| Uploads | invoice, shipment export, rate card → `POST /source-files` + import jobs |
| Tolerances | `compliance_policy` defaults (future) |
| Done | redirect dashboard |

POC: partner may upload on behalf via `X-Uploaded-By-Partner: {partner_id}` header (audited in `source_files` metadata future).
