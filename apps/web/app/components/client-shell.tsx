"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { getOrganizationProfile } from "@/lib/api";
import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";
import { usePartnerBranding } from "@/lib/partner-branding";
import { useOrgId } from "@/lib/session";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/imports", label: "Imports" },
  { href: "/discrepancies", label: "Discrepancies" },
  { href: "/account", label: "Account" },
];

type Variant = "dark" | "light";

export function ClientHeader({
  title,
  subtitle,
  variant = "dark",
}: {
  title: string;
  subtitle?: string;
  variant?: Variant;
}) {
  const { orgId } = useOrgId();
  const [company, setCompany] = useState<string | null>(null);
  const [partnerSlug, setPartnerSlug] = useState<string>(DEMO_PARTNER_SLUG);

  useEffect(() => {
    if (!orgId) {
      setCompany(null);
      setPartnerSlug(DEMO_PARTNER_SLUG);
      return;
    }
    getOrganizationProfile(orgId)
      .then((p) => {
        setCompany(p.name);
        setPartnerSlug(p.partner_id?.trim() || DEMO_PARTNER_SLUG);
      })
      .catch(() => {
        setCompany(null);
        setPartnerSlug(DEMO_PARTNER_SLUG);
      });
  }, [orgId]);

  const { branding, accent } = usePartnerBranding(partnerSlug);
  const partnerLabel = branding?.display_name ?? partnerSlug;

  const dark = variant === "dark";
  return (
    <header
      className={dark ? "border-b border-slate-800 px-6 py-5" : "border-b px-6 py-5"}
      style={{ borderBottomColor: accent }}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/"
          className={dark ? "text-sm text-slate-400 hover:text-slate-200" : "text-sm text-slate-500 hover:text-slate-800"}
        >
          Home
        </Link>
        <div className="flex items-center gap-2 text-sm">
          {branding?.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-6 w-auto object-contain" />
          ) : null}
          <span className={dark ? "text-slate-300" : "text-slate-600"}>{partnerLabel}</span>
          <span className={dark ? "text-slate-500" : "text-slate-400"}>·</span>
          <span className={dark ? "text-slate-300" : "text-slate-600"}>{company ?? "No account open"}</span>
        </div>
      </div>
      <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
      {subtitle && (
        <p className={dark ? "text-sm text-slate-400" : "text-sm text-slate-500"}>{subtitle}</p>
      )}
      <nav className="mt-4 flex flex-wrap gap-3 text-sm">
        {NAV.map((item) => (
          <Link key={item.href} href={item.href} className="hover:underline" style={{ color: accent }}>
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

export function EmptyAccount({ variant = "dark" }: { variant?: Variant }) {
  const { accent } = usePartnerBranding(DEMO_PARTNER_SLUG);
  const dark = variant === "dark";
  return (
    <p className={`px-6 py-8 text-sm ${dark ? "text-slate-400" : "text-slate-600"}`}>
      No account is open.{" "}
      <Link href={`/p/${DEMO_PARTNER_SLUG}/onboarding`} className="underline" style={{ color: accent }}>
        Start warehouse setup
      </Link>
      .
    </p>
  );
}

export function ClientShell({
  title,
  subtitle,
  variant = "dark",
  children,
}: {
  title: string;
  subtitle?: string;
  variant?: Variant;
  children: (orgId: string) => ReactNode;
}) {
  const { orgId, ready } = useOrgId();
  const dark = variant === "dark";
  return (
    <div className={dark ? "min-h-screen bg-slate-950 text-slate-50" : "min-h-screen bg-white text-slate-900"}>
      <ClientHeader title={title} subtitle={subtitle} variant={variant} />
      {!ready ? (
        <p className="px-6 py-8 text-sm text-slate-500">Loading…</p>
      ) : !orgId ? (
        <EmptyAccount variant={variant} />
      ) : (
        children(orgId)
      )}
    </div>
  );
}
