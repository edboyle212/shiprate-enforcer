"use client";

import Link from "next/link";

import { AppSidebar } from "@/app/components/client-shell";
import { KpiTile } from "@/app/components/ui/kpi-tile";
import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";
import { usePartnerBranding } from "@/lib/partner-branding";
import { useOrgId } from "@/lib/session";

export function HomeMarketing() {
  const { branding, accentStyle } = usePartnerBranding(DEMO_PARTNER_SLUG);
  const { orgId } = useOrgId();
  const displayName = branding?.display_name ?? DEMO_PARTNER_SLUG;
  const workspace = orgId ? "Your workspace" : "No account open";

  return (
    <div className="sr-app sr-shell-row" style={accentStyle}>
      <AppSidebar
        workspaceName={workspace}
        partnerSlug={DEMO_PARTNER_SLUG}
        accentStyle={accentStyle}
        displayName={displayName}
        logoUrl={branding?.logo_url}
        activeHref="/"
      />
      <div className="sr-main">
        <header style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Good morning, Ray</h1>
          <span style={{ fontSize: 13, color: "var(--ink-2)" }}>Snapshot of rate-card compliance for your warehouse.</span>
        </header>

        <section className="sr-kpi-grid">
          <KpiTile
            label="Open overcharge"
            value="$4,210.00"
            sub="calculated from rate card"
            valueClassName=""
            valueStyle={{ color: "var(--attention)" }}
          />
          <KpiTile label="Flagged rows" value="38" sub="of 1,204 shipments" />
          <KpiTile label="Open disputes" value="6" sub="$1,940.00 in play" />
          <KpiTile
            label="Recovered (90d)"
            value="$12,980.00"
            sub="across 54 disputes"
            valueStyle={{ color: "var(--pos)" }}
          />
        </section>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(280px, 100%), 1fr))", gap: 16 }}>
          <Link
            href="/dashboard"
            className="sr-panel"
            style={{ display: "flex", flexDirection: "column", gap: 8, color: "inherit" }}
          >
            <span style={{ fontSize: 14, fontWeight: 700 }}>Open the daily app</span>
            <span style={{ fontSize: 13, color: "var(--ink-2)" }}>Dashboard, imports, discrepancies, and account — four items in the sidebar.</span>
            <span className="sr-link-accent" style={{ fontSize: 13, marginTop: 8 }}>Go to dashboard →</span>
          </Link>
          <Link
            href={`/partner/${DEMO_PARTNER_SLUG}/onboarding`}
            className="sr-panel"
            style={{ display: "flex", flexDirection: "column", gap: 8, color: "inherit" }}
          >
            <span style={{ fontSize: 14, fontWeight: 700 }}>Partner setup</span>
            <span style={{ fontSize: 13, color: "var(--ink-2)" }}>Branding, export shape, carriers, and client invite — separate from daily nav.</span>
            <span className="sr-link-accent" style={{ fontSize: 13, marginTop: 8 }}>Open partner wizard →</span>
          </Link>
        </div>

        <section className="sr-panel">
          <h2 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>Recent activity</h2>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 13, color: "var(--ink-2)" }}>
            <li style={{ padding: "10px 0", borderBottom: "1px solid var(--line-2)" }}>Carrier invoice imported — 1,204 rows matched</li>
            <li style={{ padding: "10px 0", borderBottom: "1px solid var(--line-2)" }}>38 discrepancies flagged after rate-card rating</li>
            <li style={{ padding: "10px 0" }}>6 dispute drafts prepared — not sent</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
