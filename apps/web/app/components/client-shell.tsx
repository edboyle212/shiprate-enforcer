"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { getOrganizationProfile } from "@/lib/api";
import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";
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

  useEffect(() => {
    if (!orgId) {
      setCompany(null);
      return;
    }
    getOrganizationProfile(orgId)
      .then((p) => setCompany(p.name))
      .catch(() => setCompany(null));
  }, [orgId]);

  const dark = variant === "dark";
  return (
    <header className={dark ? "border-b border-slate-800 px-6 py-5" : "border-b px-6 py-5"}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/"
          className={dark ? "text-sm text-slate-400 hover:text-slate-200" : "text-sm text-slate-500 hover:text-slate-800"}
        >
          Home
        </Link>
        <p className={dark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>{company ?? "No account open"}</p>
      </div>
      <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
      {subtitle && (
        <p className={dark ? "text-sm text-slate-400" : "text-sm text-slate-500"}>{subtitle}</p>
      )}
      <nav className="mt-4 flex flex-wrap gap-3 text-sm">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={dark ? "text-emerald-400 hover:underline" : "text-emerald-700 hover:underline"}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

export function EmptyAccount({ variant = "dark" }: { variant?: Variant }) {
  const dark = variant === "dark";
  return (
    <p className={`px-6 py-8 text-sm ${dark ? "text-slate-400" : "text-slate-600"}`}>
      No account is open.{" "}
      <Link
        href={`/p/${DEMO_PARTNER_SLUG}/onboarding`}
        className={dark ? "text-emerald-400 underline" : "text-emerald-700 underline"}
      >
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
