const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

export async function savePartnerOnboarding(
  partnerId: string,
  organizationId: string,
  payload: Record<string, unknown>,
) {
  const res = await fetch(`${API_BASE}/partners/${partnerId}/onboarding`, {
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

export type PartnerOnboardingForm = {
  partner_name?: string;
  branding_mode?: string;
  export_methods?: string[];
  export_fields?: Record<string, boolean | null>;
  carriers?: string[];
  embed_mode?: string;
  ingest_mode?: string;
  is_3pl?: boolean | null;
  notes?: string;
};
