const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

export async function savePartnerOnboarding(
  partnerId: string,
  organizationId: string,
  payload: Record<string, unknown>,
) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/profile`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }
  return res.json();
}

export async function loadPartnerProfile(partnerId: string, organizationId: string) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/profile`, {
    headers: { "X-Organization-Id": organizationId },
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
    headers: { "X-Organization-Id": organizationId },
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
      headers: { "X-Organization-Id": organizationId },
    },
  );
  if (!res.ok) throw new Error(`Import job failed ${res.status}`);
  return res.json();
}

export async function saveClientOnboarding(organizationId: string, payload: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/organizations/${organizationId}/client-onboarding`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function pollEtlDrop(organizationId: string, partnerId: string) {
  const res = await fetch(`${API_BASE}/etl/poll-drop`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
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
    headers: { "X-Organization-Id": organizationId },
  });
  if (!res.ok) throw new Error(`Reporting summary failed ${res.status}`);
  return res.json() as Promise<ReportingSummary>;
}

export async function getOrganizationProfile(organizationId: string) {
  const res = await fetch(`${API_BASE}/organizations/current/profile`, {
    headers: { "X-Organization-Id": organizationId },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
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
    headers: { "X-Organization-Id": organizationId },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify({ review_status, review_comment }),
  });
  if (!res.ok) throw new Error(`Review update failed ${res.status}`);
  return res.json() as Promise<DiscrepancyDetail>;
}

export async function openDisputeCase(organizationId: string, discrepancyId: string) {
  const res = await fetch(`${API_BASE}/discrepancies/${discrepancyId}/open-case`, {
    method: "POST",
    headers: { "X-Organization-Id": organizationId },
  });
  if (!res.ok) throw new Error(`Open dispute case failed ${res.status}`);
  return res.json() as Promise<{ id: string }>;
}

export async function listDisputeCases(organizationId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases`, {
    headers: { "X-Organization-Id": organizationId },
  });
  if (!res.ok) throw new Error(`List dispute cases failed ${res.status}`);
  return res.json() as Promise<Array<{ id: string; discrepancy_id: string }>>;
}

export async function getDisputeCase(organizationId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}`, {
    headers: { "X-Organization-Id": organizationId },
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
    headers: { "X-Organization-Id": organizationId },
  });
  if (!res.ok) throw new Error(`Get organization failed ${res.status}`);
  return res.json() as Promise<OrganizationCurrent>;
}

export async function patchOrgAutonomy(organizationId: string, autonomy_tier: AutonomyTier) {
  const res = await fetch(`${API_BASE}/organizations/current`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify({ autonomy_tier }),
  });
  if (!res.ok) throw new Error(`Update autonomy failed ${res.status}`);
  return res.json();
}

export async function negotiateDisputeCase(organizationId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/negotiate`, {
    method: "POST",
    headers: { "X-Organization-Id": organizationId },
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
    headers: { "X-Organization-Id": organizationId },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify(messageId ? { message_id: messageId } : {}),
  });
  if (!res.ok) throw new Error(`Approve send failed ${res.status}`);
  return res.json();
}

export async function stopDisputeCase(organizationId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/dispute-cases/${caseId}/stop`, {
    method: "POST",
    headers: { "X-Organization-Id": organizationId },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify({ headers, kind }),
  });
  if (!res.ok) throw new Error(`Column mapping failed ${res.status}`);
  return res.json() as Promise<{ mapping: ColumnMapping; used_ai: boolean }>;
}

export async function listDiscrepancies(organizationId: string) {
  const res = await fetch(`${API_BASE}/discrepancies`, {
    headers: { "X-Organization-Id": organizationId },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
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
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
    },
    body: JSON.stringify({ import_job_id: importJobId ?? null, run_compliance: true }),
  });
  if (!res.ok) throw new Error(`Matching run failed ${res.status}`);
  return res.json() as Promise<{
    exact_matches: number;
    normalized_matches: number;
    discrepancies_created: number | null;
  }>;
}

export type TraceQueueCounts = {
  ready_to_review: number;
  live_investigations: number;
  awaiting_carrier: number;
};

export type TraceOrderRow = {
  id: string;
  external_order_id: string;
  customer_name: string;
  customer_email: string;
  carrier_code: string;
  tracking_reference: string;
  ship_date: string;
  case_id: string | null;
  case_status: string | null;
};

export type TraceCarrierContact = {
  id: string;
  carrier_code: string;
  contact_name: string;
  email: string;
  account_reference: string | null;
};

export type TraceFilingWindow = {
  days: number | null;
  months: number | null;
  uncertain: boolean;
  constant_name: string | null;
  source_note: string;
};

export type TraceRules = {
  carriers: string[];
  reasons: string[];
  evidence_kinds: string[];
  email_sent_on_confirm: boolean;
  by_carrier: Record<
    string,
    Record<
      string,
      {
        required_fields: string[];
        required_evidence: string[];
        optional_evidence: string[];
        filing_window: TraceFilingWindow;
      }
    >
  >;
};

export type TracePreview = {
  ok: boolean;
  email_subject: string | null;
  email_body: string | null;
  email_sent: boolean;
  normalized_tracking: string;
  filing_deadline: string;
  filing_window_source: string;
  filing_window_uncertain: boolean;
  recipient: TraceCarrierContact | null;
  contact_ready: boolean;
};

export type TraceClaimPacket = {
  id: string;
  details: Record<string, unknown>;
  evidence: { kind: string; filename: string; sha256_hex: string; storage_key: string }[];
  email_subject: string;
  email_body: string;
  recipient: {
    contact_name: string;
    email: string;
    account_reference: string | null;
    carrier_code: string;
  };
  email_sent: boolean;
  channel: string;
};

export class TraceApiError extends Error {
  errors: { code: string; message: string }[];

  constructor(message: string, errors: { code: string; message: string }[]) {
    super(message);
    this.errors = errors;
  }
}

async function readTraceError(res: Response): Promise<TraceApiError> {
  const body = await res.json().catch(() => null);
  const errors = body?.detail?.errors;
  if (Array.isArray(errors) && errors.length > 0) {
    return new TraceApiError(
      errors.map((error: { message?: string }) => error.message ?? "Request failed").join(" "),
      errors,
    );
  }
  const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`;
  return new TraceApiError(detail, []);
}

function orgHeaders(organizationId: string, json = false): HeadersInit {
  return json
    ? { "Content-Type": "application/json", "X-Organization-Id": organizationId }
    : { "X-Organization-Id": organizationId };
}

export async function getTraceRules(organizationId: string) {
  const res = await fetch(`${API_BASE}/tracedesk/rules`, { headers: orgHeaders(organizationId) });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<TraceRules>;
}

export async function getTraceQueue(organizationId: string, query: string) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  const suffix = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_BASE}/tracedesk/orders${suffix}`, { headers: orgHeaders(organizationId) });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<{ counts: TraceQueueCounts; orders: TraceOrderRow[] }>;
}

export async function uploadTraceOrders(organizationId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/tracedesk/orders/upload`, {
    method: "POST",
    headers: orgHeaders(organizationId),
    body: form,
  });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<{ created: number; skipped: number; errors: { row: number; message: string }[] }>;
}

export async function getTraceContacts(organizationId: string) {
  const res = await fetch(`${API_BASE}/tracedesk/carrier-contacts`, { headers: orgHeaders(organizationId) });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<{ contacts: TraceCarrierContact[] }>;
}

export async function uploadTraceContacts(organizationId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/tracedesk/carrier-contacts/upload`, {
    method: "POST",
    headers: orgHeaders(organizationId),
    body: form,
  });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<{ created: number; updated: number; errors: { row: number; message: string }[] }>;
}

export async function previewTrace(
  organizationId: string,
  orderId: string,
  payload: {
    tracking_reference: string;
    reason: string;
    length_in: number;
    width_in: number;
    height_in: number;
    contents_summary: string;
    order_reference: string;
    evidence: { kind: string; filename: string }[];
    require_contact: boolean;
  },
) {
  const res = await fetch(`${API_BASE}/tracedesk/orders/${orderId}/preview`, {
    method: "POST",
    headers: orgHeaders(organizationId, true),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<TracePreview>;
}

export async function confirmTrace(
  organizationId: string,
  orderId: string,
  fields: {
    tracking_reference: string;
    reason: string;
    length_in: string;
    width_in: string;
    height_in: string;
    contents_summary: string;
    order_reference: string;
  },
  files: { shipment_photo?: File | null; sales_invoice?: File | null; purchase_invoice?: File | null },
) {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  if (files.shipment_photo) form.append("shipment_photo", files.shipment_photo);
  if (files.sales_invoice) form.append("sales_invoice", files.sales_invoice);
  if (files.purchase_invoice) form.append("purchase_invoice", files.purchase_invoice);
  const res = await fetch(`${API_BASE}/tracedesk/orders/${orderId}/confirm`, {
    method: "POST",
    headers: orgHeaders(organizationId),
    body: form,
  });
  if (!res.ok) throw await readTraceError(res);
  return res.json() as Promise<{ case_id: string; status: string; email_sent: boolean; packet: TraceClaimPacket }>;
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
