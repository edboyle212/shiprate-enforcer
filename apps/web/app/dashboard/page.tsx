"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import { getOrganizationProfile, getReportingSummary, type OrganizationProfile, type ReportingSummary } from "@/lib/api";
import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";
import { usePartnerBranding } from "@/lib/partner-branding";

function formatMoney(minor: number) {
  return `$${(minor / 100).toFixed(2)}`;
}

function DashboardBody({ orgId }: { orgId: string }) {
  const [summary, setSummary] = useState<ReportingSummary | null>(null);
  const [profile, setProfile] = useState<OrganizationProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getReportingSummary(orgId), getOrganizationProfile(orgId)])
      .then(([s, p]) => {
        if (cancelled) return;
        setSummary(s);
        setProfile(p);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load dashboard");
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const wizardHref = `/p/${profile?.partner_id ?? DEMO_PARTNER_SLUG}/onboarding?org=${orgId}`;
  const { accent } = usePartnerBranding(profile?.partner_id ?? DEMO_PARTNER_SLUG);
  const linkStyle = { color: accent };

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi label="Discrepancies" value={summary ? String(summary.discrepancy_count) : "0"} />
        <Kpi
          label="Total overcharge"
          value={summary ? formatMoney(summary.total_overcharge_minor) : "$0.00"}
          accent
        />
        <Kpi label="Open disputes" value={summary ? String(summary.open_disputes) : "0"} />
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <p className="text-xs uppercase text-slate-500">Compliance rate</p>
          <p className="mt-2 text-3xl font-semibold">
            {summary?.compliance_rate != null ? `${(summary.compliance_rate * 100).toFixed(1)}%` : "—"}
          </p>
          {summary?.compliance_rate_note && (
            <p className="mt-2 text-xs text-slate-500">{summary.compliance_rate_note}</p>
          )}
        </div>
        <Kpi label="Recovered" value={summary ? formatMoney(summary.recovered_total_minor) : "$0.00"} />
        <Kpi label="Fee" value={summary ? formatMoney(summary.fee_total_minor) : "$0.00"} />
      </div>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-slate-300">Needs attention</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-300">
          {profile && !profile.setup_complete && (
            <li>
              Setup is unfinished.{" "}
              <Link href="/account" className="underline" style={linkStyle}>
                Finish the account profile
              </Link>{" "}
              or{" "}
              <Link href={wizardHref} className="underline" style={linkStyle}>
                continue the wizard
              </Link>
              .
            </li>
          )}
          {(summary?.discrepancy_count ?? 0) > 0 && (
            <li>
              {summary?.discrepancy_count} discrepancies to review.{" "}
              <Link href="/discrepancies" className="underline" style={linkStyle}>
                Open discrepancies
              </Link>
              .
            </li>
          )}
          {(summary?.import_job_count ?? 0) === 0 && (
            <li>
              No files imported yet.{" "}
              <Link href="/imports" className="underline" style={linkStyle}>
                Open import center
              </Link>
              .
            </li>
          )}
          {profile?.setup_complete &&
            (summary?.discrepancy_count ?? 0) === 0 &&
            (summary?.import_job_count ?? 0) > 0 && (
              <li className="text-slate-500">Nothing waiting. Compliance looks current.</li>
            )}
        </ul>
      </section>
    </main>
  );
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${accent ? "text-amber-300" : ""}`}>{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ClientShell title="Dashboard" subtitle="KPIs from deterministic compliance and dispute cases.">
      {(orgId) => <DashboardBody orgId={orgId} />}
    </ClientShell>
  );
}
