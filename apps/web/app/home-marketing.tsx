"use client";

import Link from "next/link";

import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";
import { usePartnerBranding } from "@/lib/partner-branding";

export function HomeMarketing() {
  const { branding, accent } = usePartnerBranding(DEMO_PARTNER_SLUG);
  const partnerLabel = branding?.display_name ?? "Northstar WMS";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col items-center justify-center px-6">
      <div className="flex flex-col items-center gap-3 text-center">
        {branding?.logo_url ? (
          <img src={branding.logo_url} alt="" className="h-12 w-auto object-contain" />
        ) : null}
        <h1 className="text-4xl font-semibold tracking-tight">Shiprate Enforcer</h1>
        <p className="text-sm text-slate-400">
          for <span style={{ color: accent }}>{partnerLabel}</span>
        </p>
      </div>
      <p className="mt-3 max-w-lg text-center text-slate-400">
        Parcel rate compliance — billed vs allowed, deterministic engine, multi-tenant by organization.
      </p>
      <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:flex-wrap justify-center">
        <Link
          href="/dashboard"
          className="rounded-lg px-5 py-3 text-sm font-medium text-center text-white"
          style={{ backgroundColor: accent }}
        >
          Dashboard
        </Link>
        <Link
          href="/account"
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center hover:border-slate-500"
        >
          Account
        </Link>
        <Link
          href="/imports"
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center hover:border-slate-500"
        >
          Import center
        </Link>
        <Link
          href="/discrepancies"
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center hover:border-slate-500"
        >
          Discrepancies
        </Link>
        <Link
          href={`/partner/${DEMO_PARTNER_SLUG}/onboarding`}
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center hover:border-slate-500"
        >
          Partner onboarding (demo)
        </Link>
        <Link
          href={`/partner/${DEMO_PARTNER_SLUG}/accounts`}
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center hover:border-slate-500"
        >
          Partner accounts
        </Link>
        <Link
          href={`/p/${DEMO_PARTNER_SLUG}/onboarding`}
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center hover:border-slate-500"
        >
          Client upload wizard (demo)
        </Link>
      </div>
    </div>
  );
}
