"use client";

import { useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import {
  createImportJob,
  mapInvoiceCsv,
  mapShipmentCsv,
  proposeColumnMapping,
  runMatching,
  uploadSourceFile,
  type ColumnMapping,
} from "@/lib/api";

const SAMPLE_SHIPMENTS = `tracking_number,carrier,service,dest_postal,weight_oz
1ZNORTH0000000001,UPS,GND,10001,4
`;

const SAMPLE_INVOICE = `tracking_number,charge_code,description,billed_amount
1ZNORTH0000000001,FRT,Ground parcel,15.00
`;

function ImportsBody({ orgId }: { orgId: string }) {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingMap, setPendingMap] = useState<{
    kind: "shipment_export" | "carrier_invoice";
    importJobId: string;
    csvText: string;
    mapping: ColumnMapping;
    usedAi: boolean;
  } | null>(null);

  async function onUpload(kind: "shipment_export" | "carrier_invoice" | "rate_card", file: File) {
    setError(null);
    setPendingMap(null);
    try {
      const text = await file.text();
      const source = await uploadSourceFile(orgId, kind, file);
      const job = await createImportJob(orgId, source.id, `${kind}:${source.sha256_hex}`);
      if (kind === "rate_card") {
        setStatus(`Uploaded ${file.name} (${kind})`);
        return;
      }
      const headers = text.split(/\r?\n/)[0]?.split(",") ?? [];
      const proposal = await proposeColumnMapping(
        orgId,
        headers.map((h) => h.trim()),
        kind,
      );
      setPendingMap({
        kind,
        importJobId: job.id,
        csvText: text,
        mapping: proposal.mapping,
        usedAi: proposal.used_ai,
      });
      setStatus(`Uploaded ${file.name} — confirm column mapping below.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  }

  async function acceptMapping() {
    if (!pendingMap) return;
    setError(null);
    try {
      if (pendingMap.kind === "shipment_export") {
        await mapShipmentCsv(orgId, pendingMap.importJobId, pendingMap.csvText, pendingMap.mapping);
      } else {
        await mapInvoiceCsv(orgId, pendingMap.importJobId, pendingMap.csvText, pendingMap.mapping);
      }
      setStatus(`Mapping accepted (${pendingMap.usedAi ? "AI assist" : "template"}) — rows imported.`);
      setPendingMap(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mapping failed");
    }
  }

  async function runDemoPipeline() {
    setError(null);
    try {
      const shipBlob = new Blob([SAMPLE_SHIPMENTS], { type: "text/csv" });
      const shipFile = new File([shipBlob], "shipments.csv", { type: "text/csv" });
      const shipSource = await uploadSourceFile(orgId, "shipment_export", shipFile);
      const shipJob = await createImportJob(orgId, shipSource.id, `demo-ship:${Date.now()}`);
      await mapShipmentCsv(orgId, shipJob.id, SAMPLE_SHIPMENTS);

      const invBlob = new Blob([SAMPLE_INVOICE], { type: "text/csv" });
      const invFile = new File([invBlob], "invoice.csv", { type: "text/csv" });
      const invSource = await uploadSourceFile(orgId, "carrier_invoice", invFile);
      const invJob = await createImportJob(orgId, invSource.id, `demo-inv:${Date.now()}`);
      await mapInvoiceCsv(orgId, invJob.id, SAMPLE_INVOICE);

      const match = await runMatching(orgId);
      setStatus(
        `Demo pipeline complete — matches: ${match.exact_matches + match.normalized_matches}, discrepancies: ${match.discrepancies_created ?? 0}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo pipeline failed");
    }
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-8 space-y-6">
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

      {pendingMap && (
        <div className="rounded-xl border border-slate-200 p-4 space-y-3">
          <p className="text-sm font-medium">Proposed column mapping</p>
          <p className="text-xs text-slate-500">
            Source: {pendingMap.usedAi ? "AI assist (feature-flagged)" : "default template"}
          </p>
          <ul className="space-y-1 text-xs font-mono">
            {Object.entries(pendingMap.mapping).map(([field, column]) => (
              <li key={field}>
                {field} → {column}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => void acceptMapping()}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white"
          >
            Accept mapping & import rows
          </button>
        </div>
      )}

      {status && <p className="text-sm text-emerald-700">{status}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </main>
  );
}

export default function ImportsPage() {
  return (
    <ClientShell
      title="Import center"
      subtitle="Upload source files, map CSV rows, run matching + compliance."
      variant="light"
    >
      {(orgId) => <ImportsBody orgId={orgId} />}
    </ClientShell>
  );
}
