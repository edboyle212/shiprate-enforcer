import Link from "next/link";

import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col items-center justify-center px-6">
      <h1 className="text-4xl font-semibold tracking-tight">Shiprate Enforcer</h1>
      <p className="mt-3 max-w-lg text-center text-slate-400">
        Parcel rate compliance — billed vs allowed, deterministic engine, multi-tenant by organization.
      </p>
      <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:flex-wrap justify-center">
        <Link
          href="/dashboard"
          className="rounded-lg bg-indigo-600 px-5 py-3 text-sm font-medium text-center"
        >
          Dashboard
        </Link>
        <Link
          href="/account"
          className="rounded-lg bg-indigo-500 px-5 py-3 text-sm font-medium text-center"
        >
          Account
        </Link>
        <Link
          href="/imports"
          className="rounded-lg bg-emerald-600 px-5 py-3 text-sm font-medium text-center"
        >
          Import center
        </Link>
        <Link
          href="/discrepancies"
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center"
        >
          Discrepancies
        </Link>
        <Link
          href={`/partner/${DEMO_PARTNER_SLUG}/onboarding`}
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center"
        >
          Partner onboarding (demo)
        </Link>
        <Link
          href={`/partner/${DEMO_PARTNER_SLUG}/accounts`}
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center"
        >
          Partner accounts
        </Link>
        <Link
          href={`/p/${DEMO_PARTNER_SLUG}/onboarding`}
          className="rounded-lg border border-slate-700 px-5 py-3 text-sm text-center"
        >
          Client upload wizard (demo)
        </Link>
      </div>
    </div>
  );
}
