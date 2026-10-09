"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import { KpiTile } from "@/app/components/ui/kpi-tile";
import {
  getOrganizationProfile,
  getReportingSummary,
  listDiscrepancies,
  type DiscrepancySummary,
  type OrganizationProfile,
  type ReportingSummary,
} from "@/lib/api";
import { formatMoneyMinor } from "@/lib/format-money";

function DashboardBody({ orgId }: { orgId: string }) {
  const [summary, setSummary] = useState<ReportingSummary | null>(null);
  const [profile, setProfile] = useState<OrganizationProfile | null>(null);
  const [reviewRows, setReviewRows] = useState<DiscrepancySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([getReportingSummary(orgId), getOrganizationProfile(orgId), listDiscrepancies(orgId)])
      .then(([s, p, rows]) => {
        setSummary(s);
        setProfile(p);
        setReviewRows(rows.slice(0, 3));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, [orgId]);

  useEffect(() => {
    load();
  }, [load]);

  const empty =
    !loading &&
    !error &&
    summary &&
    summary.import_job_count === 0 &&
    summary.discrepancy_count === 0;

  if (loading) {
    return (
      <div aria-busy="true" style={{ display: "flex", flexDirection: "column", gap: 22 }}>
        <div className="sr-kpi-grid">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="sr-kpi">
              <div className="sr-skeleton" style={{ height: 12, width: "60%" }} />
              <div className="sr-skeleton" style={{ height: 28, width: "40%", marginTop: 8 }} />
            </div>
          ))}
        </div>
        <div className="sr-skeleton" style={{ height: 200, borderRadius: 14 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="sr-panel" style={{ textAlign: "center", padding: 40 }}>
        <p style={{ fontWeight: 700, color: "var(--danger)" }}>Couldn&apos;t load the dashboard</p>
        <p style={{ fontSize: 13, color: "var(--ink-2)" }}>Nothing was changed on your account.</p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 16 }}>
          <button type="button" className="sr-btn-primary" onClick={() => load()}>Retry</button>
          <a href="mailto:support@shiprate.example" className="sr-btn-secondary">Contact support</a>
        </div>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="sr-panel" style={{ textAlign: "center", padding: 48 }}>
        <p style={{ fontWeight: 700 }}>No data yet</p>
        <p style={{ fontSize: 13, color: "var(--ink-2)", maxWidth: 360, margin: "8px auto 20px" }}>
          Upload a shipment export and carrier invoice to compare billed amounts against your rate card.
        </p>
        <Link href="/imports" className="sr-btn-primary">Go to import center</Link>
      </div>
    );
  }

  const carriers = profile?.carriers?.length ? profile.carriers.join(" & ") : "Carriers";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      <section className="sr-kpi-grid">
        <KpiTile
          label="Discrepancies"
          value={String(summary?.discrepancy_count ?? 0)}
          sub="flagged after rate-card rating"
        />
        <KpiTile
          label="Total overcharge"
          value={formatMoneyMinor(summary?.total_overcharge_minor ?? 0)}
          sub="calculated from rate card"
          valueStyle={{ color: "var(--attention)" }}
        />
        <KpiTile label="Open disputes" value={String(summary?.open_disputes ?? 0)} sub="drafts and active cases" />
        <KpiTile
          label="Compliance rate"
          value={summary?.compliance_rate != null ? `${(summary.compliance_rate * 100).toFixed(1)}%` : "—"}
          sub={summary?.compliance_rate_note ?? "billed within rate card"}
        />
        <KpiTile
          label="Recovered (90d)"
          value={formatMoneyMinor(summary?.recovered_total_minor ?? 0)}
          sub="credits recorded"
          valueStyle={{ color: "var(--pos)" }}
        />
      </section>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(min(320px, 100%), 1fr))",
          gap: 18,
          alignItems: "start",
        }}
      >
        <section className="sr-panel" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Overcharge by carrier</h2>
          <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>
            Breakdown appears when carrier-level reporting is enabled. Totals above are calculated from rate card.
          </p>
          <div style={{ fontSize: 12, color: "var(--ink-3)", borderTop: "1px solid var(--line-2)", paddingTop: 12 }}>
            Carriers on file: <strong style={{ color: "var(--ink-2)" }}>{carriers}</strong>
          </div>
        </section>

        <section className="sr-panel" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <h2 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Needs review</h2>
            <Link href="/discrepancies" className="sr-link-accent" style={{ fontSize: 12 }}>View all</Link>
          </div>
          {reviewRows.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>No flagged rows waiting.</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {reviewRows.map((row) => (
                <li
                  key={row.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "12px 0",
                    borderBottom: "1px solid var(--line-2)",
                    fontSize: 13,
                  }}
                >
                  <span className="sr-mono" style={{ fontSize: 12 }}>{row.id.slice(0, 8)}…</span>
                  <span className="sr-mono" style={{ color: "var(--attention)", fontWeight: 600 }}>
                    +{formatMoneyMinor(row.variance_minor, row.currency_code)}
                  </span>
                  <Link href={`/discrepancies/${row.id}`} className="sr-link-accent" style={{ fontSize: 12 }}>
                    Review
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ClientShell
      title="Dashboard"
      subtitle="KPIs from deterministic compliance and dispute cases."
      headerAction={
        <Link href="/imports" className="sr-btn-primary">
          Import files
        </Link>
      }
    >
      {(orgId) => <DashboardBody orgId={orgId} />}
    </ClientShell>
  );
}
