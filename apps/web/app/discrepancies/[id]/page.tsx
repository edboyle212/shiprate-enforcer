"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getDiscrepancy,
  openDisputeCase,
  patchDiscrepancyReview,
  type DiscrepancyDetail,
} from "@/lib/api";

const DEMO_ORG_KEY = "shiprate_demo_org_id";

export default function DiscrepancyDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const [orgId, setOrgId] = useState("");
  const [row, setRow] = useState<DiscrepancyDetail | null>(null);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<"open" | "approved" | "rejected" | "hold">("open");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(DEMO_ORG_KEY);
    if (stored) setOrgId(stored);
  }, []);

  async function load() {
    if (!orgId) {
      setError("Set organization ID.");
      return;
    }
    setError(null);
    try {
      const data = await getDiscrepancy(orgId, id);
      setRow(data);
      setStatus(data.review_status as typeof status);
      setComment(data.review_comment ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  async function submitReview() {
    if (!orgId || !comment.trim()) {
      setError("Review comment is required.");
      return;
    }
    try {
      const updated = await patchDiscrepancyReview(orgId, id, status, comment.trim());
      setRow(updated);
      setMessage("Review saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    }
  }

  async function onOpenCase() {
    if (!orgId) return;
    try {
      await openDisputeCase(orgId, id);
      setMessage("Dispute case opened (draft-only workflow).");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Open case failed");
    }
  }

  function formatMoney(minor: number, currency: string) {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-5">
        <Link href="/discrepancies" className="text-sm text-slate-400 hover:text-slate-200">
          ← Discrepancies
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Discrepancy detail</h1>
        <p className="font-mono text-xs text-slate-500">{id}</p>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-8 space-y-6">
        <label className="block text-sm">
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
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm"
        >
          Load
        </button>

        {error && <p className="text-sm text-red-400">{error}</p>}
        {message && <p className="text-sm text-emerald-400">{message}</p>}

        {row && (
          <>
            <div className="rounded-xl border border-slate-800 p-5 space-y-2 text-sm">
              <p>
                <span className="text-slate-400">Billed:</span>{" "}
                {formatMoney(row.billed_amount_minor, row.currency_code)}
              </p>
              <p>
                <span className="text-slate-400">Allowed:</span>{" "}
                {formatMoney(row.allowed_amount_minor, row.currency_code)}
              </p>
              <p>
                <span className="text-slate-400">Variance:</span>{" "}
                <span className="text-amber-300">{formatMoney(row.variance_minor, row.currency_code)}</span>
              </p>
              <p>
                <span className="text-slate-400">Reasons:</span> {row.reason_codes.join(", ")}
              </p>
              <p>
                <span className="text-slate-400">Review:</span> {row.review_status}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 p-5">
              <p className="text-sm font-medium mb-2">Rating trace summary</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs">
                {JSON.stringify(row.trace_summary, null, 2)}
              </pre>
            </div>

            <div className="rounded-xl border border-slate-800 p-5 space-y-3">
              <p className="text-sm font-medium">Review workflow</p>
              <select
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={status}
                onChange={(e) => setStatus(e.target.value as typeof status)}
              >
                <option value="open">open</option>
                <option value="approved">approved</option>
                <option value="rejected">rejected</option>
                <option value="hold">hold</option>
              </select>
              <textarea
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                rows={3}
                placeholder="Review comment (required)"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button
                type="button"
                onClick={() => void submitReview()}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium"
              >
                Save review
              </button>
            </div>

            <button
              type="button"
              onClick={() => void onOpenCase()}
              className="w-full rounded-lg border border-amber-600 px-4 py-3 text-sm text-amber-200"
            >
              Open dispute case (draft only — no auto-send)
            </button>
          </>
        )}
      </main>
    </div>
  );
}
