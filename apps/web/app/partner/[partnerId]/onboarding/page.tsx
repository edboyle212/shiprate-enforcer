"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { KpiTile } from "@/app/components/ui/kpi-tile";
import { DEFAULT_ACCENT, partnerAccentStyle } from "@/lib/accent-vars";
import { loadPartnerProfile, PartnerOnboardingForm, savePartnerOnboarding } from "@/lib/api";

const STEPS = [
  "Identity",
  "Branding",
  "Export",
  "Fields",
  "Carriers",
  "Embed",
  "Ingest",
  "3PL",
  "Invite",
];

const inputStyle = {
  display: "block",
  width: "100%",
  marginTop: 6,
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid var(--line)",
  fontSize: 14,
};

export default function PartnerOnboardingPage() {
  const params = useParams<{ partnerId: string }>();
  const [step, setStep] = useState(0);
  const [orgId, setOrgId] = useState("");
  const [form, setForm] = useState<PartnerOnboardingForm>({
    export_methods: [],
    carriers: [],
    export_fields: {},
  });
  const [status, setStatus] = useState<string | null>(null);

  const previewAccent = form.primary_color ?? DEFAULT_ACCENT;
  const previewStyle = useMemo(() => partnerAccentStyle(previewAccent), [previewAccent]);

  useEffect(() => {
    if (!orgId || !params.partnerId) return;
    loadPartnerProfile(params.partnerId, orgId).then((data) => {
      if (data) {
        const { branding, ...rest } = data as PartnerOnboardingForm & { branding?: Record<string, string> };
        setForm({
          ...rest,
          branding_mode: branding?.branding_mode ?? rest.branding_mode,
          logo_url: branding?.logo_url,
          primary_color: branding?.primary_color,
          support_email: branding?.support_email,
          display_name: branding?.display_name ?? rest.display_name,
        });
      }
    });
  }, [orgId, params.partnerId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!orgId) {
      setStatus("Set a dev organization UUID (X-Organization-Id).");
      return;
    }
    try {
      const payload = { ...form };
      if (step === STEPS.length - 1 && !payload.client_invite_base_url) {
        payload.client_invite_base_url =
          typeof window !== "undefined"
            ? `${window.location.origin}/p/${params.partnerId}/onboarding`
            : `/p/${params.partnerId}/onboarding`;
      }
      await savePartnerOnboarding(params.partnerId, orgId, payload);
      setStatus("Saved partner profile.");
      if (step < STEPS.length - 1) setStep(step + 1);
    } catch {
      setStatus("Could not reach API — check API is running.");
    }
  }

  const inviteUrl =
    form.client_invite_base_url ??
    (typeof window !== "undefined"
      ? `${window.location.origin}/p/${params.partnerId}/onboarding`
      : `/p/${params.partnerId}/onboarding`);

  const displayName = form.display_name ?? params.partnerId;

  return (
    <div className="sr-app" style={{ minHeight: "100vh" }}>
      <header
        style={{
          background: "var(--surface)",
          borderBottom: "1px solid var(--line)",
          padding: "16px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>Shiprate Enforcer · Partner setup</span>
          <h1 style={{ margin: "4px 0 0", fontSize: 18, fontWeight: 700 }}>{displayName}</h1>
        </div>
        <Link href={`/partner/${params.partnerId}/accounts`} className="sr-link-accent" style={{ fontSize: 13 }}>
          Client accounts
        </Link>
      </header>

      <div style={{ overflowX: "auto", borderBottom: "1px solid var(--line)", background: "var(--surface)" }}>
        <ol
          style={{
            display: "flex",
            gap: 16,
            listStyle: "none",
            margin: 0,
            padding: "14px 24px",
            minWidth: "max-content",
          }}
        >
          {STEPS.map((label, i) => {
            const done = i < step;
            const current = i === step;
            return (
              <li key={label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <span
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 12,
                    border: done || current ? "none" : "1px solid var(--line)",
                    ...(done || current
                      ? { background: previewAccent, color: "#fff" }
                      : { background: "transparent", color: "var(--ink-3)" }),
                  }}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span style={{ fontWeight: current ? 700 : 500, color: current ? "var(--ink)" : "var(--ink-3)" }}>{label}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <form onSubmit={onSubmit}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: step === 1 ? "1fr 1fr" : "1fr",
              gap: 24,
              alignItems: "start",
            }}
          >
            <div className="sr-panel" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <label style={{ fontSize: 13 }}>
                Dev organization ID (API auth during setup)
                <input
                  style={inputStyle}
                  value={orgId}
                  onChange={(e) => setOrgId(e.target.value)}
                  placeholder="uuid from POST /api/v1/organizations"
                />
              </label>

              {step === 0 && (
                <label style={{ fontSize: 13 }}>
                  Partner name
                  <input
                    style={inputStyle}
                    value={form.partner_name ?? ""}
                    onChange={(e) => setForm({ ...form, partner_name: e.target.value })}
                  />
                </label>
              )}

              {step === 1 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
                  <label>
                    Display name
                    <input
                      style={inputStyle}
                      value={form.display_name ?? ""}
                      onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                    />
                  </label>
                  <label>
                    Logo URL
                    <input
                      style={inputStyle}
                      value={form.logo_url ?? ""}
                      onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
                      placeholder="https://…"
                    />
                  </label>
                  <label>
                    Accent color
                    <div style={{ display: "flex", gap: 10, marginTop: 6, alignItems: "center" }}>
                      <input
                        type="color"
                        value={form.primary_color ?? DEFAULT_ACCENT}
                        onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                        aria-label="Accent color"
                      />
                      <input
                        style={{ ...inputStyle, marginTop: 0, flex: 1 }}
                        value={form.primary_color ?? DEFAULT_ACCENT}
                        onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                      />
                    </div>
                  </label>
                  <label>
                    Support email
                    <input
                      style={inputStyle}
                      type="email"
                      value={form.support_email ?? ""}
                      onChange={(e) => setForm({ ...form, support_email: e.target.value })}
                    />
                  </label>
                  <label>
                    Branding mode
                    <select
                      style={inputStyle}
                      value={form.branding_mode ?? ""}
                      onChange={(e) => setForm({ ...form, branding_mode: e.target.value })}
                    >
                      <option value="">Select…</option>
                      <option value="co_brand">Co-brand</option>
                      <option value="white_label">White label</option>
                    </select>
                  </label>
                </div>
              )}

              {step === 2 && (
                <fieldset style={{ border: "none", margin: 0, padding: 0, fontSize: 13 }}>
                  <legend style={{ fontWeight: 600, marginBottom: 8 }}>Shipment export methods</legend>
                  {["api", "scheduled_report", "ad_hoc_csv", "varies_by_warehouse"].map((m) => (
                    <label key={m} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
                      <input
                        type="checkbox"
                        checked={form.export_methods?.includes(m)}
                        onChange={(e) => {
                          const set = new Set(form.export_methods);
                          if (e.target.checked) set.add(m);
                          else set.delete(m);
                          setForm({ ...form, export_methods: [...set] });
                        }}
                      />
                      {m}
                    </label>
                  ))}
                </fieldset>
              )}

              {step === 3 && (
                <fieldset style={{ border: "none", margin: 0, padding: 0, fontSize: 13 }}>
                  <legend style={{ fontWeight: 600, marginBottom: 8 }}>Fields present</legend>
                  {[
                    "tracking",
                    "billed_weight",
                    "actual_weight",
                    "dims",
                    "service",
                    "carrier_account",
                    "ship_date",
                    "dest_postal",
                    "bill_to_client",
                  ].map((field) => (
                    <label key={field} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
                      <input
                        type="checkbox"
                        checked={form.export_fields?.[field] === true}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            export_fields: {
                              ...form.export_fields,
                              [field]: e.target.checked ? true : null,
                            },
                          })
                        }
                      />
                      {field}
                    </label>
                  ))}
                </fieldset>
              )}

              {step === 4 && (
                <label style={{ fontSize: 13 }}>
                  Carriers billed (comma-separated)
                  <input
                    style={inputStyle}
                    defaultValue={form.carriers?.join(", ")}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        carriers: e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                  />
                </label>
              )}

              {step === 5 && (
                <label style={{ fontSize: 13 }}>
                  Embed mode
                  <select
                    style={inputStyle}
                    value={form.embed_mode ?? "companion_url_only"}
                    onChange={(e) => setForm({ ...form, embed_mode: e.target.value })}
                  >
                    <option value="companion_url_only">Companion URL</option>
                    <option value="iframe">iframe</option>
                    <option value="smarttask">SmartTask</option>
                    <option value="marketplace">Marketplace</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </label>
              )}

              {step === 6 && (
                <label style={{ fontSize: 13 }}>
                  Ingest mode
                  <select
                    style={inputStyle}
                    value={form.ingest_mode ?? ""}
                    onChange={(e) => setForm({ ...form, ingest_mode: e.target.value })}
                  >
                    <option value="partner_uploads_client_data">Partner uploads client data (POC)</option>
                    <option value="client_self_upload">Client self upload (rollout)</option>
                  </select>
                </label>
              )}

              {step === 7 && (
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <input
                    type="checkbox"
                    checked={form.is_3pl === true}
                    onChange={(e) => setForm({ ...form, is_3pl: e.target.checked ? true : null })}
                  />
                  One WMS tenant maps to many bill-to accounts (3PL)
                </label>
              )}

              {step === 8 && (
                <div style={{ fontSize: 13 }}>
                  <p>Share this URL with warehouse clients:</p>
                  <code
                    style={{
                      display: "block",
                      padding: 12,
                      background: "var(--surface-2)",
                      borderRadius: 8,
                      wordBreak: "break-all",
                      fontSize: 12,
                    }}
                  >
                    {inviteUrl}
                  </code>
                </div>
              )}

              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <button type="button" className="sr-btn-secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>
                  Back
                </button>
                <button type="submit" className="sr-btn-primary" style={previewStyle}>
                  {step === STEPS.length - 1 ? "Finish" : "Save & continue"}
                </button>
              </div>
              {status && <p style={{ fontSize: 13, color: "var(--pos)" }}>{status}</p>}
            </div>

            {step === 1 && (
              <div className="sr-panel" style={previewStyle}>
                <p style={{ fontSize: 12, color: "var(--ink-3)", margin: "0 0 12px" }}>Live preview</p>
                <div
                  style={{
                    background: "var(--surface)",
                    borderRadius: 10,
                    border: "1px solid var(--line)",
                    padding: 12,
                    marginBottom: 14,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {form.logo_url ? (
                    <img src={form.logo_url} alt="" style={{ height: 24, objectFit: "contain" }} />
                  ) : (
                    <span style={{ width: 24, height: 24, borderRadius: 6, background: "var(--accent)" }} />
                  )}
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{displayName}</div>
                    <div style={{ fontSize: 10, color: "var(--ink-3)" }}>Shiprate Enforcer</div>
                  </div>
                </div>
                <div style={{ display: "grid", gap: 10 }}>
                  <KpiTile label="Discrepancies" value="38" sub="preview" />
                  <button type="button" className="sr-btn-primary" style={{ width: "fit-content" }}>Primary action</button>
                </div>
              </div>
            )}
          </div>
        </form>

        <p style={{ marginTop: 32, fontSize: 13 }}>
          <Link href="/" className="sr-link-accent">Back to home</Link>
        </p>
      </main>
    </div>
  );
}
