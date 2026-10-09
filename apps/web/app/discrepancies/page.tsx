"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import { StatusPill } from "@/app/components/ui/status-pill";
import { listDiscrepancies, type DiscrepancySummary } from "@/lib/api";
import { formatMoneyMinor } from "@/lib/format-money";

function DiscrepanciesBody({ orgId }: { orgId: string }) {
  const [rows, setRows] = useState<DiscrepancySummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listDiscrepancies(orgId)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load discrepancies"))
      .finally(() => setLoading(false));
  }, [orgId]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      if (statusFilter !== "all" && row.review_status !== statusFilter) return false;
      if (search.trim() && !row.id.toLowerCase().includes(search.trim().toLowerCase())) return false;
      return true;
    });
  }, [rows, search, statusFilter]);

  const totalOver = filtered.reduce((s, r) => s + r.variance_minor, 0);
  const openCount = filtered.filter((r) => r.review_status === "open").length;

  if (loading) {
    return (
      <div aria-busy="true" className="sr-panel">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="sr-skeleton" style={{ height: 40, marginBottom: 8 }} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="sr-panel" style={{ textAlign: "center", padding: 40 }}>
        <p style={{ fontWeight: 700, color: "var(--danger)" }}>Couldn&apos;t load discrepancies</p>
        <p style={{ fontSize: 13, color: "var(--ink-2)" }}>No rows were changed.</p>
        <button type="button" className="sr-btn-primary" style={{ marginTop: 16 }} onClick={() => load()}>
          Retry
        </button>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="sr-panel" style={{ textAlign: "center", padding: 48 }}>
        <p style={{ fontWeight: 700, color: "var(--pos)" }}>Nothing flagged</p>
        <p style={{ fontSize: 13, color: "var(--ink-2)", maxWidth: 400, margin: "8px auto 20px" }}>
          Every matched shipment was billed within the rate card.
        </p>
        <Link href="/imports" className="sr-btn-primary">Import an invoice</Link>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          padding: 14,
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 12,
        }}
      >
        <label style={{ fontSize: 13, flex: "1 1 160px" }}>
          <span style={{ display: "block", fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>Search</span>
          <input
            type="search"
            placeholder="Tracking or ID"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}
          />
        </label>
        <label style={{ fontSize: 13 }}>
          <span style={{ display: "block", fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>Status</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="approved">Approved</option>
            <option value="hold">On hold</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
      </div>

      <p style={{ fontSize: 13, color: "var(--ink-2)", margin: 0 }}>
        {filtered.length} rows ·{" "}
        <span className="sr-mono" style={{ color: "var(--attention)" }}>{formatMoneyMinor(totalOver)}</span> total
        overcharge · {openCount} open disputes
      </p>

      <div className="sr-table-wrap">
        <table className="sr-table">
          <thead>
            <tr>
              <th>Record</th>
              <th className="sr-money">Billed</th>
              <th className="sr-money">Allowed</th>
              <th className="sr-money">Variance</th>
              <th>Reasons</th>
              <th>Review</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link href={`/discrepancies/${row.id}`} className="sr-mono sr-link-accent" style={{ fontSize: 12 }}>
                    {row.id.slice(0, 12)}…
                  </Link>
                </td>
                <td className="sr-money sr-mono">{formatMoneyMinor(row.billed_amount_minor, row.currency_code)}</td>
                <td className="sr-money sr-mono">{formatMoneyMinor(row.allowed_amount_minor, row.currency_code)}</td>
                <td className="sr-money sr-mono" style={{ color: "var(--attention)", fontWeight: 600 }}>
                  +{formatMoneyMinor(row.variance_minor, row.currency_code)}
                </td>
                <td style={{ fontSize: 12 }}>{row.reason_codes.join(", ")}</td>
                <td><StatusPill status={row.review_status} /></td>
                <td>
                  <Link href={`/discrepancies/${row.id}`} className="sr-link-accent" style={{ fontSize: 12 }}>
                    Review
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DiscrepanciesPage() {
  return (
    <ClientShell
      title="Discrepancies"
      subtitle="Billed vs allowed after deterministic rating."
      headerAction={
        <button type="button" className="sr-btn-secondary" disabled title="Export coming soon">
          Export
        </button>
      }
    >
      {(orgId) => <DiscrepanciesBody orgId={orgId} />}
    </ClientShell>
  );
}
