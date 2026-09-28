"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-4">
        <p className="text-sm text-slate-400">Partner admin</p>
        <h1 className="text-2xl font-semibold">Onboarding — {params.partnerId}</h1>
        <p className="mt-2 text-sm">
          <Link href={`/partner/${params.partnerId}/accounts`} className="text-emerald-400 hover:underline">
            Client accounts
          </Link>
        </p>
      </header>
      <main className="mx-auto max-w-2xl px-6 py-10">
        <ol className="mb-8 flex flex-wrap gap-2 text-xs">
          {STEPS.map((label, i) => (
            <li
              key={label}
              className={`rounded-full px-3 py-1 ${i === step ? "bg-emerald-600" : "bg-slate-800"}`}
            >
              {label}
            </li>
          ))}
        </ol>

        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <label className="block text-sm">
            Dev organization ID (for API auth header during setup)
            <input
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="uuid from POST /api/v1/organizations"
            />
          </label>

          {step === 0 && (
            <label className="block text-sm">
              Partner name
              <input
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                value={form.partner_name ?? ""}
                onChange={(e) => setForm({ ...form, partner_name: e.target.value })}
              />
            </label>
          )}

          {step === 1 && (
            <div className="space-y-3 text-sm">
              <label className="block">
                Branding mode
                <select
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={form.branding_mode ?? ""}
                  onChange={(e) => setForm({ ...form, branding_mode: e.target.value })}
                >
                  <option value="">Select…</option>
                  <option value="co_brand">Co-brand</option>
                  <option value="white_label">White label</option>
                </select>
              </label>
              <label className="block">
                Display name
                <input
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={form.display_name ?? ""}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                />
              </label>
              <label className="block">
                Primary color
                <input
                  type="color"
                  className="mt-1 h-10 w-full"
                  value={form.primary_color ?? "#059669"}
                  onChange={(e) => setForm({ ...form, primary_color: e.target.value })}
                />
              </label>
            </div>
          )}

          {step === 2 && (
            <fieldset className="text-sm">
              <legend className="mb-2">Shipment export methods</legend>
              {["api", "scheduled_report", "ad_hoc_csv", "varies_by_warehouse"].map((m) => (
                <label key={m} className="flex items-center gap-2 py-1">
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
            <fieldset className="text-sm">
              <legend className="mb-2">Fields present (unknown = unset)</legend>
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
                <label key={field} className="flex items-center gap-2 py-1">
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
            <label className="block text-sm">
              Carriers billed (comma-separated)
              <input
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
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
            <label className="block text-sm">
              Embed mode
              <select
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
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
            <label className="block text-sm">
              Ingest mode
              <select
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                value={form.ingest_mode ?? ""}
                onChange={(e) => setForm({ ...form, ingest_mode: e.target.value })}
              >
                <option value="partner_uploads_client_data">Partner uploads client data (POC)</option>
                <option value="client_self_upload">Client self upload (rollout)</option>
              </select>
            </label>
          )}

          {step === 7 && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_3pl === true}
                onChange={(e) => setForm({ ...form, is_3pl: e.target.checked ? true : null })}
              />
              One WMS tenant maps to many bill-to accounts (3PL) — TBD
            </label>
          )}

          {step === 8 && (
            <div className="space-y-2 text-sm">
              <p>Share this URL with warehouse clients at rollout:</p>
              <code className="block break-all rounded bg-slate-950 p-3 text-emerald-300">{inviteUrl}</code>
              <p className="text-slate-400">POC: you can upload on their behalf instead of sending this link.</p>
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              className="rounded-md border border-slate-600 px-4 py-2 text-sm"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              Back
            </button>
            <button type="submit" className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium">
              {step === STEPS.length - 1 ? "Finish" : "Save & continue"}
            </button>
          </div>
          {status && <p className="text-sm text-emerald-400">{status}</p>}
        </form>

        <p className="mt-8 text-sm text-slate-500">
          <Link href="/">Back to home</Link>
        </p>
      </main>
    </div>
  );
}
