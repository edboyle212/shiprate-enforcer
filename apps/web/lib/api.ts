const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

const DEFAULT_DEMO_ORG_ID = process.env.NEXT_PUBLIC_DEFAULT_DEMO_ORG_ID?.trim() || null;

export function tenantHeaders(organizationId: string, extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { "X-Organization-Id": organizationId, ...extra };
  if (DEFAULT_DEMO_ORG_ID && organizationId === DEFAULT_DEMO_ORG_ID) {
    headers.Authorization = `Bearer shiprate-test:try-demo:${organizationId}`;
  }
  return headers;
}

export async function savePartnerOnboarding(
  partnerId: string,
  organizationId: string,
  payload: Record<string, unknown>,
) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/profile`, {
    method: "PUT",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }
  return res.json();
}

export async function loadPartnerProfile(partnerId: string, organizationId: string) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/profile`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function loadPublicBranding(partnerId: string) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/public-branding`);
  if (!res.ok) return null;
  return res.json();
}

export async function createOrganization(name: string, slug: string, partnerId?: string) {
  const res = await fetch(`${API_BASE}/organizations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, slug, partner_id: partnerId }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json() as Promise<{ id: string; slug: string }>;
}

export async function uploadSourceFile(
  organizationId: string,
  kind: "shipment_export" | "carrier_invoice" | "rate_card",
  file: File,
) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/source-files?kind=${kind}`, {
    method: "POST",
    headers: tenantHeaders(organizationId),
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed ${res.status}`);
  return res.json() as Promise<{ id: string; sha256_hex: string }>;
}

export async function createImportJob(organizationId: string, sourceFileId: string, idempotencyKey: string) {
  const res = await fetch(
    `${API_BASE}/import-jobs?source_file_id=${sourceFileId}&idempotency_key=${encodeURIComponent(idempotencyKey)}`,
    {
      method: "POST",
      headers: tenantHeaders(organizationId),
    },
  );
  if (!res.ok) throw new Error(`Import job failed ${res.status}`);
  return res.json();
}

export async function saveClientOnboarding(organizationId: string, payload: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/organizations/${organizationId}/client-onboarding`, {
    method: "PUT",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function pollEtlDrop(organizationId: string, partnerId: string) {
  const res = await fetch(`${API_BASE}/etl/poll-drop`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({ partner_id: partnerId }),
  });
  if (!res.ok) throw new Error(`ETL poll failed ${res.status}`);
  return res.json();
}

export type DiscrepancySummary = {
  id: string;
  billed_amount_minor: number;
  allowed_amount_minor: number;
  variance_minor: number;
  currency_code: string;
  reason_codes: string[];
  review_status: string;
  created_at: string;
};

export type DiscrepancyDetail = DiscrepancySummary & {
  trace_summary: Record<string, unknown>;
  review_comment: string | null;
  match_id: string | null;
  shipment_id: string | null;
  carrier_invoice_line_id: string | null;
};

export type ReportingSummary = {
  discrepancy_count: number;
  total_overcharge_minor: number;
  open_disputes: number;
  recovered_total_minor: number;
  fee_total_minor: number;
  import_job_count: number;
  compliance_rate: number | null;
  compliance_rate_note: string | null;
};

export type ProfilePerson = {
  name: string;
  email: string;
  role: "owner" | "admin" | "billing" | "viewer";
};

export type OrganizationProfile = {
  id: string;
  name: string;
  slug: string;
  partner_id: string | null;
  contacts: {
    primary_name: string;
    primary_email: string;
    billing_email: string;
    disputes_email: string;
  };
  people: ProfilePerson[];
  carriers: string[];
  tolerances: { absolute_minor: number; percent: number };
  autonomy_tier: AutonomyTier;
  carrier_billing_emails: Record<string, string>;
  recovery_fee_bps: number;
  setup_complete: boolean;
};

export type PartnerAccountRow = {
  id: string;
  name: string;
  slug: string;
  created_at: string | null;
  setup_complete: boolean;
};

export type AutonomyTier = "draft" | "approve_each" | "autonomous";

export type DisputeMessage = {
  id: string;
  direction: "outbound" | "inbound";
  email_subject: string;
  email_body: string;
  status: string;
  round_number: number;
  offered_amount_minor: number | null;
  denied: boolean;
  created_at: string;
  sent_at: string | null;
};

export type DisputeCaseDetail = {
  id: string;
  discrepancy_id: string;
  claim_amount_minor: number;
  currency_code: string;
  status: string;
  autonomy_tier: AutonomyTier;
  fee_bps: number;
  recovered_amount_minor: number | null;
  fee_amount_minor: number | null;
  created_at: string;
  messages: DisputeMessage[];
};

export type ColumnMapping = Record<string, string>;

export async function getReportingSummary(organizationId: string) {
  const res = await fetch(`${API_BASE}/reporting/summary`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Reporting summary failed ${res.status}`);
  return res.json() as Promise<ReportingSummary>;
}

export async function getOrganizationProfile(organizationId: string) {
  const res = await fetch(`${API_BASE}/organizations/current/profile`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Profile load failed ${res.status}`);
  return res.json() as Promise<OrganizationProfile>;
}

export async function patchOrganizationProfile(
  organizationId: string,
  payload: Partial<{
    name: string;
    contacts: OrganizationProfile["contacts"];
    people: ProfilePerson[];
    carriers: string[];
    tolerances: { absolute_minor: number; percent: number };
    autonomy_tier: AutonomyTier;
    carrier_billing_emails: Record<string, string>;
  }>,
) {
  const res = await fetch(`${API_BASE}/organizations/current/profile`, {
    method: "PATCH",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Profile save failed ${res.status}`);
  return res.json() as Promise<OrganizationProfile>;
}

export async function listPartnerAccounts(partnerId: string) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/accounts`);
  if (!res.ok) throw new Error(`Account list failed ${res.status}`);
  return res.json() as Promise<PartnerAccountRow[]>;
}

export async function createPartnerAccount(partnerId: string, name: string) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/accounts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Create account failed ${res.status}`);
  return res.json() as Promise<PartnerAccountRow>;
}

export async function getDiscrepancy(organizationId: string, id: string) {
  const res = await fetch(`${API_BASE}/discrepancies/${id}`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Get discrepancy failed ${res.status}`);
  return res.json() as Promise<DiscrepancyDetail>;
}

export async function patchDiscrepancyReview(
  organizationId: string,
  id: string,
  review_status: "open" | "approved" | "rejected" | "hold",
  review_comment: string,
) {
  const res = await fetch(`${API_BASE}/discrepancies/${id}`, {
    method: "PATCH",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({ review_status, review_comment }),
  });
  if (!res.ok) throw new Error(`Review update failed ${res.status}`);
  return res.json() as Promise<DiscrepancyDetail>;
}

export async function openDisputeCase(organizationId: string, discrepancyId: string) {
  const res = await fetch(`${API_BASE}/discrepancies/${discrepancyId}/open-case`, {
    method: "POST",
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Open dispute case failed ${res.status}`);
  return res.json() as Promise<{ id: string }>;
}

export async function listDisputeCases(organizationId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`List dispute cases failed ${res.status}`);
  return res.json() as Promise<Array<{ id: string; discrepancy_id: string }>>;
}

export async function getDisputeCase(organizationId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Get dispute case failed ${res.status}`);
  return res.json() as Promise<DisputeCaseDetail>;
}

export type OrganizationCurrent = {
  id: string;
  settings_json: {
    autonomy_tier?: AutonomyTier;
    carrier_billing_emails?: Record<string, string>;
    recovery_fee_bps?: number;
  };
};

export async function getCurrentOrganization(organizationId: string) {
  const res = await fetch(`${API_BASE}/organizations/current`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Get organization failed ${res.status}`);
  return res.json() as Promise<OrganizationCurrent>;
}

export async function patchOrgAutonomy(organizationId: string, autonomy_tier: AutonomyTier) {
  const res = await fetch(`${API_BASE}/organizations/current`, {
    method: "PATCH",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({ autonomy_tier }),
  });
  if (!res.ok) throw new Error(`Update autonomy failed ${res.status}`);
  return res.json();
}

export async function negotiateDisputeCase(organizationId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/negotiate`, {
    method: "POST",
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Negotiate failed ${res.status}`);
  return res.json();
}

export type OutboundMailStatus = {
  configured: boolean;
  from_address: string | null;
};

export async function getDisputeOutboundMail(organizationId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/outbound-mail`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Outbound mail status failed ${res.status}`);
  return res.json() as Promise<OutboundMailStatus>;
}

export async function approveSendDispute(
  organizationId: string,
  caseId: string,
  messageId?: string,
) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/approve-send`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify(messageId ? { message_id: messageId } : {}),
  });
  if (!res.ok) throw new Error(`Approve send failed ${res.status}`);
  return res.json();
}

export async function stopDisputeCase(organizationId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/stop`, {
    method: "POST",
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`Stop case failed ${res.status}`);
  return res.json();
}

export async function recordDisputeCredit(
  organizationId: string,
  caseId: string,
  recovered_amount_minor: number,
) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/record-credit`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({ recovered_amount_minor }),
  });
  if (!res.ok) throw new Error(`Record credit failed ${res.status}`);
  return res.json();
}

export async function postCarrierReply(
  organizationId: string,
  caseId: string,
  payload: { subject: string; body: string; offered_amount_minor?: number; denied?: boolean },
) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/replies`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Post reply failed ${res.status}`);
  return res.json();
}

export async function proposeColumnMapping(
  organizationId: string,
  headers: string[],
  kind: "shipment_export" | "carrier_invoice" = "shipment_export",
) {
  const res = await fetch(`${API_BASE}/ai/map-columns`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({ headers, kind }),
  });
  if (!res.ok) throw new Error(`Column mapping failed ${res.status}`);
  return res.json() as Promise<{ mapping: ColumnMapping; used_ai: boolean }>;
}

export async function listDiscrepancies(organizationId: string) {
  const res = await fetch(`${API_BASE}/discrepancies`, {
    headers: tenantHeaders(organizationId),
  });
  if (!res.ok) throw new Error(`List discrepancies failed ${res.status}`);
  return res.json() as Promise<DiscrepancySummary[]>;
}

export async function mapShipmentCsv(
  organizationId: string,
  importJobId: string,
  csvText: string,
  mapping?: ColumnMapping,
) {
  const res = await fetch(`${API_BASE}/imports/map-csv`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({
      import_job_id: importJobId,
      csv_text: csvText,
      mapping: mapping
        ? {
            tracking_number: mapping.tracking_number,
            carrier_code: mapping.carrier_code,
            service_code: mapping.service_code,
            dest_postal: mapping.dest_postal,
            weight_oz: mapping.weight_oz,
          }
        : undefined,
    }),
  });
  if (!res.ok) throw new Error(`Map shipments failed ${res.status}`);
  return res.json();
}

export async function mapInvoiceCsv(
  organizationId: string,
  importJobId: string,
  csvText: string,
  mapping?: ColumnMapping,
) {
  const res = await fetch(`${API_BASE}/imports/map-invoice-csv`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({
      import_job_id: importJobId,
      csv_text: csvText,
      mapping: mapping
        ? {
            tracking_number: mapping.tracking_number,
            charge_code: mapping.charge_code,
            description: mapping.description,
            billed_amount: mapping.billed_amount,
          }
        : undefined,
    }),
  });
  if (!res.ok) throw new Error(`Map invoice failed ${res.status}`);
  return res.json();
}

export async function runMatching(organizationId: string, importJobId?: string) {
  const res = await fetch(`${API_BASE}/matching/run`, {
    method: "POST",
    headers: tenantHeaders(organizationId, { "Content-Type": "application/json" }),
    body: JSON.stringify({ import_job_id: importJobId ?? null, run_compliance: true }),
  });
  if (!res.ok) throw new Error(`Matching run failed ${res.status}`);
  return res.json() as Promise<{
    exact_matches: number;
    normalized_matches: number;
    discrepancies_created: number | null;
  }>;
}

export type PartnerOnboardingForm = {
  partner_name?: string;
  branding_mode?: string;
  display_name?: string;
  logo_url?: string;
  primary_color?: string;
  support_email?: string;
  export_methods?: string[];
  export_fields?: Record<string, boolean | null>;
  carriers?: string[];
  embed_mode?: string;
  ingest_mode?: string;
  is_3pl?: boolean | null;
  notes?: string;
  client_invite_base_url?: string;
};
