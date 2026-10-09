"use client";

import { useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import { StatusPill } from "@/app/components/ui/status-pill";
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

const FIELD_LABELS: Record<string, string> = {
  tracking_number: "Tracking number",
  carrier_code: "Carrier",
  service_code: "Service",
  dest_postal: "Destination postal",
  weight_oz: "Weight (oz)",
  charge_code: "Charge code",
  description: "Description",
  billed_amount: "Billed amount",
};

type RowConfirm = Record<string, boolean>;

function ImportsBody({ orgId }: { orgId: string }) {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentLog, setRecentLog] = useState<{ ok: boolean; text: string }[]>([]);
  const [uploadedKinds, setUploadedKinds] = useState<Record<string, "uploaded" | "pending">>({});
  const [pendingMap, setPendingMap] = useState<{
    kind: "shipment_export" | "carrier_invoice";
    importJobId: string;
    csvText: string;
    mapping: ColumnMapping;
    usedAi: boolean;
    headers: string[];
    sampleRow: string[];
    confirmed: RowConfirm;
  } | null>(null);

  async function onUpload(kind: "shipment_export" | "carrier_invoice" | "rate_card", file: File) {
    setError(null);
    setPendingMap(null);
    try {
      const text = await file.text();
      const source = await uploadSourceFile(orgId, kind, file);
      const job = await createImportJob(orgId, source.id, `${kind}:${source.sha256_hex}`);
      if (kind === "rate_card") {
        setUploadedKinds((k) => ({ ...k, rate_card: "uploaded" }));
        setRecentLog((log) => [{ ok: true, text: `${file.name} uploaded — rate card stored.` }, ...log]);
        setStatus(`Uploaded ${file.name} (${kind})`);
        return;
      }
      const lines = text.split(/\r?\n/).filter(Boolean);
      const headers = lines[0]?.split(",").map((h) => h.trim()) ?? [];
      const sampleRow = lines[1]?.split(",").map((c) => c.trim()) ?? [];
      const proposal = await proposeColumnMapping(orgId, headers, kind);
      const confirmed: RowConfirm = {};
      for (const field of Object.keys(proposal.mapping)) confirmed[field] = false;
      setUploadedKinds((k) => ({ ...k, [kind]: kind === "shipment_export" ? "uploaded" : "pending" }));
      setPendingMap({
        kind,
        importJobId: job.id,
        csvText: text,
        mapping: proposal.mapping,
        usedAi: proposal.used_ai,
        headers,
        sampleRow,
        confirmed,
      });
      setStatus(`Uploaded ${file.name} — confirm column mapping below.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setRecentLog((log) => [
        { ok: false, text: e instanceof Error ? e.message : "Upload failed" },
        ...log,
      ]);
    }
  }

  function updateMappingField(field: string, column: string) {
    if (!pendingMap) return;
    setPendingMap({
      ...pendingMap,
      mapping: { ...pendingMap.mapping, [field]: column },
      confirmed: { ...pendingMap.confirmed, [field]: true },
    });
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
      setRecentLog((log) => [
        {
          ok: true,
          text: `Mapping confirmed (${pendingMap.usedAi ? "suggested columns reviewed" : "template"}) — rows imported. Amounts read verbatim.`,
        },
        ...log,
      ]);
      setStatus(`Mapping confirmed — rows imported.`);
      setUploadedKinds((k) => ({ ...k, [pendingMap.kind]: "uploaded" }));
      setPendingMap(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Mapping failed";
      setError(msg);
      setRecentLog((log) => [{ ok: false, text: msg }, ...log]);
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
      setRecentLog((log) => [
        {
          ok: true,
          text: `Demo pipeline — matches: ${match.exact_matches + match.normalized_matches}, discrepancies: ${match.discrepancies_created ?? 0}`,
        },
        ...log,
      ]);
      setStatus("Demo pipeline complete.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo pipeline failed");
    }
  }

  const tiles = [
    { kind: "shipment_export" as const, title: "Shipment export", hint: "Warehouse WMS export" },
    { kind: "carrier_invoice" as const, title: "Carrier invoice", hint: "Billed amounts CSV" },
    { kind: "rate_card" as const, title: "Rate card", hint: "Contract / tariff" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
          gap: 14,
        }}
      >
        {tiles.map(({ kind, title, hint }) => {
          const state = uploadedKinds[kind];
          const needsMapping = pendingMap?.kind === kind;
          return (
            <div
              key={kind}
              className="sr-panel"
              style={{
                borderStyle: needsMapping ? "solid" : undefined,
                borderColor: needsMapping ? "var(--accent)" : undefined,
                borderWidth: needsMapping ? 2 : undefined,
              }}
            >
              <p style={{ margin: "0 0 4px", fontWeight: 700, fontSize: 14 }}>{title}</p>
              <p style={{ margin: "0 0 12px", fontSize: 12, color: "var(--ink-3)" }}>{hint}</p>
              {state === "uploaded" && !needsMapping ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <StatusPill status="uploaded" />
                </div>
              ) : (
                <label
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 8,
                    border: "1px dashed var(--line)",
                    borderRadius: 10,
                    padding: 20,
                    cursor: "pointer",
                    fontSize: 13,
                    color: "var(--ink-2)",
                  }}
                >
                  <span aria-hidden>↑</span>
                  Drop CSV or{" "}
                  <span className="sr-link-accent">browse</span>
                  <input
                    type="file"
                    accept=".csv,.xlsx"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void onUpload(kind, file);
                    }}
                  />
                </label>
              )}
            </div>
          );
        })}
      </section>

      {pendingMap && (
        <section className="sr-panel" style={{ padding: 0, overflow: "hidden" }}>
          <div
            style={{
              background: "var(--hold-bg)",
              padding: "12px 16px",
              fontSize: 13,
              color: "var(--hold)",
              fontWeight: 600,
            }}
          >
            Suggested — not saved yet
          </div>
          <div className="sr-table-wrap" style={{ border: "none", borderRadius: 0 }}>
            <table className="sr-table">
              <thead>
                <tr>
                  <th>Your column</th>
                  <th>Maps to field</th>
                  <th>Sample</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(pendingMap.mapping).map(([field, column]) => {
                  const colIndex = pendingMap.headers.indexOf(column);
                  const sample = colIndex >= 0 ? pendingMap.sampleRow[colIndex] ?? "—" : "—";
                  const isConfirmed = pendingMap.confirmed[field];
                  return (
                    <tr key={field}>
                      <td className="sr-mono">{column}</td>
                      <td>
                        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
                          <span className="sr-only">{FIELD_LABELS[field] ?? field}</span>
                          <select
                            value={column}
                            onChange={(e) => updateMappingField(field, e.target.value)}
                            style={{
                              padding: "6px 8px",
                              borderRadius: 8,
                              border: "1px solid var(--line)",
                              fontSize: 13,
                            }}
                          >
                            {pendingMap.headers.map((h) => (
                              <option key={h} value={h}>{h}</option>
                            ))}
                          </select>
                        </label>
                      </td>
                      <td className="sr-mono" style={{ color: "var(--ink-3)" }}>{sample}</td>
                      <td>
                        <StatusPill status={isConfirmed ? "confirmed" : "suggested"} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              justifyContent: "space-between",
              alignItems: "center",
              padding: 16,
              background: "var(--surface-2)",
              borderTop: "1px solid var(--line)",
            }}
          >
            <p style={{ margin: 0, fontSize: 12, color: "var(--ink-2)" }}>
              Billed amounts are read verbatim from your file — never altered before you confirm mapping.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="sr-btn-secondary" onClick={() => setPendingMap(null)}>Cancel</button>
              <button type="button" className="sr-btn-primary" onClick={() => void acceptMapping()}>
                Confirm mapping &amp; import
              </button>
            </div>
          </div>
        </section>
      )}

      <button type="button" className="sr-btn-secondary" onClick={() => void runDemoPipeline()}>
        Run sample CSV pipeline (needs approved rate card)
      </button>

      {status && <p style={{ fontSize: 13, color: "var(--pos)" }}>{status}</p>}
      {error && <p style={{ fontSize: 13, color: "var(--danger)" }}>{error}</p>}

      <section className="sr-panel">
        <h2 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>Recent imports</h2>
        {recentLog.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>No imports logged this session.</p>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 13 }}>
            {recentLog.map((entry, i) => (
              <li
                key={i}
                style={{
                  padding: "10px 0",
                  borderBottom: "1px solid var(--line-2)",
                  color: entry.ok ? "var(--ink-2)" : "var(--danger)",
                }}
              >
                {entry.text}
              </li>
            ))}
          </ul>
        )}
        <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 12 }}>
          Example failure: 14 rows skipped — missing tracking number
        </p>
      </section>
    </div>
  );
}

export default function ImportsPage() {
  return (
    <ClientShell title="Import center" subtitle="Upload source files and confirm column mapping before save.">
      {(orgId) => <ImportsBody orgId={orgId} />}
    </ClientShell>
  );
}
