"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  createImportJob,
  createOrganization,
  mapInvoiceCsv,
  mapShipmentCsv,
  runMatching,
  uploadSourceFile,
} from "@/lib/api";

const DEMO_ORG_KEY = "shiprate_demo_org_id";

const SAMPLE_SHIPMENTS = `tracking_number,carrier,service,dest_postal,weight_oz
1Z999RLS0000000001,UPS,GND,10001,4
`;

const SAMPLE_INVOICE = `tracking_number,charge_code,description,billed_amount
1Z999RLS0000000001,FRT,Ground,15.00
`;

export default function ImportsPage() {
  const [orgId, setOrgId] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(DEMO_ORG_KEY);
    if (stored) setOrgId(stored);
  }, []);

  async function ensureOrg() {
    if (orgId) return orgId;
    const org = await createOrganization("Demo warehouse", `demo-${Date.now()}`, "jasci");
    setOrgId(org.id);
    window.localStorage.setItem(DEMO_ORG_KEY, org.id);
    return org.id;
  }

  async function onUpload(kind: "shipment_export" | "carrier_invoice" | "rate_card", file: File) {
    setError(null);
    try {
      const id = await ensureOrg();
      const source = await uploadSourceFile(id, kind, file);
      await createImportJob(id, source.id, `${kind}:${source.sha256_hex}`);
      setStatus(`Uploaded ${file.name} (${kind})`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  }

  async function runDemoPipeline() {
    setError(null);
    try {
      const id = await ensureOrg();
      const shipBlob = new Blob([SAMPLE_SHIPMENTS], { type: "text/csv" });
      const shipFile = new File([shipBlob], "shipments.csv", { type: "text/csv" });
      const shipSource = await uploadSourceFile(id, "shipment_export", shipFile);
      const shipJob = await createImportJob(id, shipSource.id, `demo-ship:${Date.now()}`);
      await mapShipmentCsv(id, shipJob.id, SAMPLE_SHIPMENTS);

      const invBlob = new Blob([SAMPLE_INVOICE], { type: "text/csv" });
      const invFile = new File([invBlob], "invoice.csv", { type: "text/csv" });
      const invSource = await uploadSourceFile(id, "carrier_invoice", invFile);
      const invJob = await createImportJob(id, invSource.id, `demo-inv:${Date.now()}`);
      await mapInvoiceCsv(id, invJob.id, SAMPLE_INVOICE);

      const match = await runMatching(id);
      setStatus(
        `Demo pipeline complete — matches: ${match.exact_matches + match.normalized_matches}, discrepancies: ${match.discrepancies_created ?? 0}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo pipeline failed");
    }
  }

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b px-6 py-5">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">
          ← Home
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Import center</h1>
        <p className="text-sm text-slate-500">Upload source files, map CSV rows, run matching + compliance.</p>
      </header>
      <main className="mx-auto max-w-xl px-6 py-8 space-y-6">
        <label className="block text-sm">
          Organization ID
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2 font-mono text-xs"
            value={orgId}
            onChange={(e) => {
              setOrgId(e.target.value);
              window.localStorage.setItem(DEMO_ORG_KEY, e.target.value);
            }}
          />
        </label>

        <div className="space-y-3">
          <p className="text-sm font-medium">Upload</p>
          {(["shipment_export", "carrier_invoice", "rate_card"] as const).map((kind) => (
            <label key={kind} className="flex items-center justify-between rounded-lg border px-4 py-3 text-sm">
              <span>{kind.replace("_", " ")}</span>
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onUpload(kind, file);
                }}
              />
            </label>
          ))}
        </div>

        <button
          type="button"
          onClick={() => void runDemoPipeline()}
          className="w-full rounded-lg bg-emerald-600 px-4 py-3 text-sm font-medium text-white"
        >
          Run sample CSV pipeline (needs approved rate card)
        </button>

        {status && <p className="text-sm text-emerald-700">{status}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        <p className="text-xs text-slate-500">
          API: POST /source-files, /import-jobs, /imports/map-csv, /imports/map-invoice-csv, POST /matching/run
        </p>
      </main>
    </div>
  );
}
