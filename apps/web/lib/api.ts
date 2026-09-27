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
  compliance_rate: number | null;
  compliance_rate_note: string | null;
};

export type ColumnMapping = Record<string, string>;

export async function getReportingSummary(organizationId: string) {
  const res = await fetch(`${API_BASE}/reporting/summary`, {
    headers: { "X-Organization-Id": organizationId },
  });
  if (!res.ok) throw new Error(`Reporting summary failed ${res.status}`);
  return res.json() as Promise<ReportingSummary>;
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
