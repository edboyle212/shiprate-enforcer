"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listDiscrepancies, type DiscrepancySummary } from "@/lib/api";

const DEMO_ORG_KEY = "shiprate_demo_org_id";

export default function DiscrepanciesPage() {
  const [orgId, setOrgId] = useState("");
  const [rows, setRows] = useState<DiscrepancySummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(DEMO_ORG_KEY);
    if (stored) setOrgId(stored);
  }, []);

  async function refresh() {
    if (!orgId) {
      setError("Set an organization ID (create one on Imports).");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await listDiscrepancies(orgId);
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load discrepancies");
    } finally {
      setLoading(false);
    }
  }

  function saveOrg() {
    window.localStorage.setItem(DEMO_ORG_KEY, orgId);
    void refresh();
  }

  function formatMoney(minor: number, currency: string) {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-5">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← Home
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Discrepancies</h1>
        <p className="text-sm text-slate-400">Billed vs allowed after deterministic rating.</p>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm">
            Organization ID
            <input
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="UUID from POST /organizations"
            />
          </label>
          <button
            type="button"
            onClick={saveOrg}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium"
          >
            Save & refresh
          </button>
        </div>
        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
        {loading && <p className="text-sm text-slate-400">Loading…</p>}
        {!loading && rows.length === 0 && (
          <p className="text-sm text-slate-400">
            No discrepancies yet. Upload shipments and invoices, run matching, then compliance.
          </p>
        )}
        {rows.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="px-4 py-3">Billed</th>
                  <th className="px-4 py-3">Allowed</th>
                  <th className="px-4 py-3">Variance</th>
                  <th className="px-4 py-3">Reasons</th>
                  <th className="px-4 py-3">Review</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-slate-800">
                    <td className="px-4 py-3">
                      <Link href={`/discrepancies/${row.id}`} className="text-emerald-400 hover:underline">
                        {formatMoney(row.billed_amount_minor, row.currency_code)}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{formatMoney(row.allowed_amount_minor, row.currency_code)}</td>
                    <td className="px-4 py-3 text-amber-300">
                      {formatMoney(row.variance_minor, row.currency_code)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{row.reason_codes.join(", ")}</td>
                    <td className="px-4 py-3 text-xs">{row.review_status}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{row.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
