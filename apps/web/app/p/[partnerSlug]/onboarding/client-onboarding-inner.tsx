"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  createImportJob,
  createOrganization,
  loadPublicBranding,
  saveClientOnboarding,
  uploadSourceFile,
} from "@/lib/api";
import { writeOrgId } from "@/lib/session";

const STEPS = ["Organization", "Carriers", "Uploads", "Policy", "Done"];

const UPLOAD_KINDS = [
  { label: "Carrier invoices", kind: "carrier_invoice" as const },
  { label: "Shipment export", kind: "shipment_export" as const },
  { label: "Rate card / contract", kind: "rate_card" as const },
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
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPublicBranding(params.partnerSlug).then(setBranding);
  }, [params.partnerSlug]);

  const accent = branding?.primary_color ?? "#0f766e";

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
      setUploadStatus(`Uploaded ${file.name} (${kind})`);
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

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b px-6 py-6" style={{ borderBottomColor: accent }}>
        <div className="flex items-center gap-3">
          {branding?.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-8 w-auto object-contain" />
          ) : null}
          <p className="text-sm text-slate-500">{branding?.display_name ?? params.partnerSlug}</p>
        </div>
        <h1 className="text-2xl font-semibold">Warehouse rate compliance setup</h1>
      </header>
      <main className="mx-auto max-w-xl px-6 py-10">
        <ol className="mb-8 flex flex-wrap gap-2 text-xs">
          {STEPS.map((label, i) => (
            <li
              key={label}
              className={`rounded-full px-3 py-1 ${i === step ? "text-white" : "bg-slate-100"}`}
              style={i === step ? { backgroundColor: accent } : undefined}
            >
              {label}
            </li>
          ))}
        </ol>

        {step === 0 && (
          <div className="space-y-4">
            <label className="block text-sm">
              Organization name
              <input
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
              />
            </label>
            {orgId && (
              <p className="text-xs text-slate-500">
                Org ID: <code>{orgId}</code>
              </p>
            )}
          </div>
        )}

        {step === 1 && (
          <label className="block text-sm">
            Carriers you bill with (comma-separated)
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              value={carriers}
              onChange={(e) => setCarriers(e.target.value)}
              placeholder="UPS, FedEx, USPS"
            />
          </label>
        )}

        {step === 2 && (
          <div className="space-y-6">
            {UPLOAD_KINDS.map(({ label, kind }) => (
              <label key={kind} className="block rounded-lg border border-dashed border-slate-300 p-4 text-sm">
                {label}
                <input
                  type="file"
                  className="mt-2 block w-full text-xs"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void onUpload(kind, f);
                  }}
                />
              </label>
            ))}
            {uploadStatus && <p className="text-sm text-emerald-700">{uploadStatus}</p>}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        )}

        {step === 3 && (
          <p className="text-sm text-slate-600">
            Default tolerances: $5.00 absolute or 2% per line (editable in admin later). Click continue to save.
          </p>
        )}

        {step === 4 && (
          <p className="text-sm text-slate-600">
            Setup complete. Mapping confirmation and compliance runs continue in the import center (next slice).
          </p>
        )}

        {error && step !== 2 && <p className="mt-4 text-sm text-red-600">{error}</p>}

        <div className="mt-8 flex justify-between">
          <button
            type="button"
            className="text-sm text-slate-600 disabled:opacity-40"
            disabled={step === 0}
            onClick={() => setStep(step - 1)}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded-md px-4 py-2 text-sm text-white"
            style={{ backgroundColor: accent }}
            onClick={() => {
              if (step === 3) void finishOnboarding();
              else setStep(Math.min(step + 1, STEPS.length - 1));
            }}
          >
            {step === 3 ? "Save & finish" : step === STEPS.length - 1 ? "Done" : "Next"}
          </button>
        </div>

        <p className="mt-10 text-sm">
          <Link href="/" className="underline" style={{ color: accent }}>
            Home
          </Link>
        </p>
      </main>
    </div>
  );
}
