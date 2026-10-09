"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusPill } from "@/app/components/ui/status-pill";
import { DEFAULT_ACCENT, partnerAccentStyle } from "@/lib/accent-vars";
import {
  createImportJob,
  createOrganization,
  loadPublicBranding,
  saveClientOnboarding,
  uploadSourceFile,
} from "@/lib/api";
import { writeOrgId } from "@/lib/session";

const STEPS = ["Warehouse", "Carriers", "Upload", "Dashboard"];

const UPLOAD_KINDS = [
  { label: "Carrier invoice", kind: "carrier_invoice" as const, required: true },
  { label: "Shipment export", kind: "shipment_export" as const, required: true },
  { label: "Rate card / contract", kind: "rate_card" as const, required: false },
];

export default function ClientOnboardingInner() {
  const params = useParams<{ partnerSlug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [step, setStep] = useState(0);
  const [orgId, setOrgId] = useState(searchParams.get("org") ?? "");
  const [orgName, setOrgName] = useState("");
  const [carriers, setCarriers] = useState("");
  const [branding, setBranding] = useState<{
    display_name?: string;
    primary_color?: string;
    logo_url?: string;
  } | null>(null);
  const [uploadState, setUploadState] = useState<Record<string, "idle" | "uploaded">>({});
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPublicBranding(params.partnerSlug).then(setBranding);
  }, [params.partnerSlug]);

  const accentStyle = partnerAccentStyle(branding?.primary_color ?? DEFAULT_ACCENT);
  const displayName = branding?.display_name ?? params.partnerSlug;

  async function ensureOrg() {
    if (orgId) return orgId;
    const slug = orgName.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 48) || "warehouse";
    const org = await createOrganization(orgName || slug, slug, params.partnerSlug);
    setOrgId(org.id);
    writeOrgId(org.id);
    return org.id;
  }

  async function onUpload(kind: (typeof UPLOAD_KINDS)[number]["kind"], file: File) {
    setError(null);
    try {
      const id = await ensureOrg();
      const source = await uploadSourceFile(id, kind, file);
      await createImportJob(id, source.id, `${kind}:${source.sha256_hex}`);
      setUploadState((s) => ({ ...s, [kind]: "uploaded" }));
      setUploadStatus(`Uploaded ${file.name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  }

  async function finishOnboarding() {
    setError(null);
    try {
      const id = await ensureOrg();
      await saveClientOnboarding(id, {
        org_name: orgName,
        carriers: carriers.split(",").map((s) => s.trim()).filter(Boolean),
        tolerances: { absolute_minor: 500, percent: 2 },
      });
      writeOrgId(id);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not finish setup");
    }
  }

  const inputStyle = {
    display: "block",
    width: "100%",
    marginTop: 6,
    padding: "8px 10px",
    borderRadius: 8,
    border: "1px solid var(--line)",
    fontSize: 14,
  };

  return (
    <div className="sr-app" style={{ minHeight: "100vh", ...accentStyle }}>
      <header style={{ background: "var(--surface)", borderBottom: "1px solid var(--line)", padding: "20px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          {branding?.logo_url ? (
            <img src={branding.logo_url} alt="" style={{ height: 32, objectFit: "contain" }} />
          ) : (
            <span style={{ width: 32, height: 32, borderRadius: 8, background: "var(--accent)" }} />
          )}
          <div>
            <div style={{ fontWeight: 700 }}>{displayName}</div>
            <div style={{ fontSize: 11, color: "var(--ink-3)" }}>Shiprate Enforcer</div>
          </div>
        </div>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Warehouse rate compliance setup</h1>
      </header>

      <div style={{ overflowX: "auto", borderBottom: "1px solid var(--line)", background: "var(--surface)" }}>
        <ol style={{ display: "flex", gap: 20, listStyle: "none", margin: 0, padding: "14px 24px", minWidth: "max-content" }}>
          {STEPS.map((label, i) => {
            const done = i < step;
            const current = i === step;
            return (
              <li key={label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                <span
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: 11,
                    background: done || current ? "var(--accent)" : "transparent",
                    color: done || current ? "var(--accent-ink)" : "var(--ink-3)",
                    border: done || current ? "none" : "1px solid var(--line)",
                  }}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span style={{ fontWeight: current ? 700 : 500 }}>{label}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <main style={{ maxWidth: 640, margin: "0 auto", padding: "32px 24px" }}>
        {step === 0 && (
          <div className="sr-panel">
            <label style={{ fontSize: 13 }}>
              Warehouse name
              <input style={inputStyle} value={orgName} onChange={(e) => setOrgName(e.target.value)} />
            </label>
            {orgId && (
              <p style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 12 }}>
                Org ID: <code className="sr-mono">{orgId}</code>
              </p>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="sr-panel">
            <label style={{ fontSize: 13 }}>
              Carriers you bill with (comma-separated)
              <input
                style={inputStyle}
                value={carriers}
                onChange={(e) => setCarriers(e.target.value)}
                placeholder="UPS, FedEx, USPS"
              />
            </label>
          </div>
        )}

        {step === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {UPLOAD_KINDS.map(({ label, kind, required }) => (
              <div key={kind} className="sr-panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <div>
                  <p style={{ margin: 0, fontWeight: 600, fontSize: 14 }}>{label}</p>
                  <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--ink-3)" }}>{required ? "Required" : "Optional"}</p>
                </div>
                {uploadState[kind] === "uploaded" ? (
                  <StatusPill status="uploaded" />
                ) : (
                  <label className="sr-btn-secondary" style={{ cursor: "pointer", margin: 0 }}>
                    Upload
                    <input
                      type="file"
                      accept=".csv,.xlsx"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void onUpload(kind, f);
                      }}
                    />
                  </label>
                )}
              </div>
            ))}
            <p style={{ fontSize: 12, color: "var(--ink-2)" }}>
              Amounts are read verbatim from your files. You will confirm column mapping next in the import center.
            </p>
            {uploadStatus && <p style={{ fontSize: 13, color: "var(--pos)" }}>{uploadStatus}</p>}
            {error && <p style={{ fontSize: 13, color: "var(--danger)" }}>{error}</p>}
          </div>
        )}

        {step === 3 && (
          <div className="sr-panel">
            <p style={{ fontSize: 14 }}>Setup complete. Continue to the dashboard or open imports to confirm mapping.</p>
          </div>
        )}

        {error && step !== 2 && <p style={{ marginTop: 16, fontSize: 13, color: "var(--danger)" }}>{error}</p>}

        <div style={{ marginTop: 24, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <button type="button" className="sr-btn-secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>
            Back
          </button>
          <div style={{ display: "flex", gap: 10 }}>
            {step === 2 && (
              <Link href="/imports" className="sr-btn-secondary">Continue to mapping</Link>
            )}
            {step === 2 && (
              <button type="button" className="sr-btn-secondary" onClick={() => router.push("/dashboard")}>
                Skip to dashboard
              </button>
            )}
            <button
              type="button"
              className="sr-btn-primary"
              onClick={() => {
                if (step === 3) void finishOnboarding();
                else if (step === 2) setStep(3);
                else setStep(Math.min(step + 1, STEPS.length - 1));
              }}
            >
              {step === 3 ? "Save & finish" : "Continue"}
            </button>
          </div>
        </div>

        <p style={{ marginTop: 32, fontSize: 13 }}>
          <Link href="/" className="sr-link-accent">Home</Link>
        </p>
      </main>
    </div>
  );
}
