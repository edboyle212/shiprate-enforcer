"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";

import { getOrganizationProfile } from "@/lib/api";
import { partnerAccentStyle } from "@/lib/accent-vars";
import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";
import { usePartnerBranding } from "@/lib/partner-branding";
import { useOrgId } from "@/lib/session";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/imports", label: "Imports" },
  { href: "/discrepancies", label: "Discrepancies" },
  { href: "/account", label: "Account" },
];

function NavIcon({ name }: { name: string }) {
  const stroke = "currentColor";
  if (name === "Dashboard") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" aria-hidden>
        <path d="M3 3v18h18" />
        <path d="M7 15l4-5 3 3 4-6" />
      </svg>
    );
  }
  if (name === "Imports") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" aria-hidden>
        <path d="M12 16V4" />
        <path d="M7 9l5-5 5 5" />
        <path d="M20 16v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-3" />
      </svg>
    );
  }
  if (name === "Discrepancies") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" aria-hidden>
        <path d="M4 6h16" />
        <path d="M4 12h16" />
        <path d="M4 18h10" />
      </svg>
    );
  }
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" aria-hidden>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  );
}

export function AppSidebar({
  activeHref,
  workspaceName,
  partnerSlug,
  accentStyle,
  displayName,
  logoUrl,
}: {
  activeHref?: string;
  workspaceName: string;
  partnerSlug: string;
  accentStyle: CSSProperties;
  displayName: string;
  logoUrl?: string;
}) {
  const pathname = usePathname();
  const active = activeHref ?? pathname;

  return (
    <aside className="sr-sidebar" style={accentStyle}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: 9, padding: "4px 6px" }}>
        {logoUrl ? (
          <img src={logoUrl} alt="" style={{ height: 24, width: "auto", objectFit: "contain" }} />
        ) : (
          <span style={{ width: 24, height: 24, borderRadius: 7, background: "var(--accent)", flexShrink: 0 }} />
        )}
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{displayName}</span>
          <span style={{ fontSize: 10.5, color: "var(--ink-3)" }}>Shiprate Enforcer</span>
        </div>
      </Link>
      <nav style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`sr-nav-item${active === item.href || active?.startsWith(item.href + "/") ? " active" : ""}`}
          >
            <NavIcon name={item.label} />
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="sr-workspace-chip">
        <span style={{ fontSize: 11, color: "var(--ink-3)" }}>Workspace</span>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{workspaceName}</span>
      </div>
    </aside>
  );
}

export function EmptyAccount() {
  return (
    <p style={{ fontSize: 14, color: "var(--ink-2)", padding: "32px 0" }}>
      No account is open.{" "}
      <Link href={`/p/${DEMO_PARTNER_SLUG}/onboarding`} className="sr-link-accent">
        Start warehouse setup
      </Link>
      .
    </p>
  );
}

export function ClientShell({
  title,
  subtitle,
  headerAction,
  children,
}: {
  title: string;
  subtitle?: string;
  headerAction?: ReactNode;
  children: (orgId: string) => ReactNode;
}) {
  const { orgId, ready } = useOrgId();
  const [company, setCompany] = useState<string>("No account open");
  const [partnerSlug, setPartnerSlug] = useState(DEMO_PARTNER_SLUG);

  useEffect(() => {
    if (!orgId) {
      setCompany("No account open");
      setPartnerSlug(DEMO_PARTNER_SLUG);
      return;
    }
    getOrganizationProfile(orgId)
      .then((p) => {
        setCompany(p.name);
        setPartnerSlug(p.partner_id?.trim() || DEMO_PARTNER_SLUG);
      })
      .catch(() => {
        setCompany("No account open");
        setPartnerSlug(DEMO_PARTNER_SLUG);
      });
  }, [orgId]);

  const { branding, accentStyle } = usePartnerBranding(partnerSlug);
  const displayName = branding?.display_name ?? partnerSlug;

  return (
    <div className="sr-app sr-shell-row" style={accentStyle}>
      <AppSidebar
        workspaceName={company}
        partnerSlug={partnerSlug}
        accentStyle={partnerAccentStyle(branding?.primary_color)}
        displayName={displayName}
        logoUrl={branding?.logo_url}
      />
      <div className="sr-main">
        <header
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 14,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: "-0.01em" }}>{title}</h1>
            {subtitle ? <span style={{ fontSize: 13, color: "var(--ink-2)" }}>{subtitle}</span> : null}
          </div>
          {headerAction}
        </header>
        {!ready ? (
          <p style={{ fontSize: 14, color: "var(--ink-3)" }} aria-busy="true">Loading…</p>
        ) : !orgId ? (
          <EmptyAccount />
        ) : (
          children(orgId)
        )}
      </div>
    </div>
  );
}
