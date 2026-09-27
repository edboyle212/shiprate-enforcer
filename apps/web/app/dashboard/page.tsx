"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getReportingSummary, type ReportingSummary } from "@/lib/api";

const DEMO_ORG_KEY = "shiprate_demo_org_id";

export default function DashboardPage() {
  const [orgId, setOrgId] = useState("");
  const [summary, setSummary] = useState<ReportingSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(DEMO_ORG_KEY);
    if (stored) setOrgId(stored);
  }, []);

  async function load() {
    if (!orgId) {
      setError("Set organization ID (create one on Imports).");
      return;
    }
    setError(null);
    try {
      window.localStorage.setItem(DEMO_ORG_KEY, orgId);
      const data = await getReportingSummary(orgId);
      setSummary(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    }
  }

  function formatMoney(minor: number) {
    return `$${(minor / 100).toFixed(2)}`;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-5">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-200">
          ← Home
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-400">KPIs from deterministic compliance and dispute cases.</p>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm">
            Organization ID
            <input
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium"
          >
            Refresh
          </button>
        </div>
        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
        {summary && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <p className="text-xs uppercase text-slate-500">Discrepancies</p>
              <p className="mt-2 text-3xl font-semibold">{summary.discrepancy_count}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <p className="text-xs uppercase text-slate-500">Total overcharge</p>
              <p className="mt-2 text-3xl font-semibold text-amber-300">
                {formatMoney(summary.total_overcharge_minor)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <p className="text-xs uppercase text-slate-500">Open disputes</p>
              <p className="mt-2 text-3xl font-semibold">{summary.open_disputes}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <p className="text-xs uppercase text-slate-500">Compliance rate</p>
              <p className="mt-2 text-3xl font-semibold">
                {summary.compliance_rate != null
                  ? `${(summary.compliance_rate * 100).toFixed(1)}%`
                  : "—"}
              </p>
              {summary.compliance_rate_note && (
                <p className="mt-2 text-xs text-slate-500">{summary.compliance_rate_note}</p>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
