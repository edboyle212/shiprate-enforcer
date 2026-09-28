"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import { listDiscrepancies, type DiscrepancySummary } from "@/lib/api";

function DiscrepanciesBody({ orgId }: { orgId: string }) {
  const [rows, setRows] = useState<DiscrepancySummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listDiscrepancies(orgId)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load discrepancies"))
      .finally(() => setLoading(false));
  }, [orgId]);

  function formatMoney(minor: number, currency: string) {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
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
  );
}

export default function DiscrepanciesPage() {
  return (
    <ClientShell title="Discrepancies" subtitle="Billed vs allowed after deterministic rating.">
      {(orgId) => <DiscrepanciesBody orgId={orgId} />}
    </ClientShell>
  );
}
