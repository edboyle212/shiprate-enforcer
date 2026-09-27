"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

const UPLOAD_STEPS = ["Invoices", "Shipment export", "Rate card / contract"];

export default function ClientOnboardingPage() {
  const params = useParams<{ partnerSlug: string }>();
  const [step, setStep] = useState(0);

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b px-6 py-6">
        <p className="text-sm text-slate-500">Client onboarding</p>
        <h1 className="text-2xl font-semibold">{params.partnerSlug} — warehouse setup</h1>
      </header>
      <main className="mx-auto max-w-xl px-6 py-10">
        <p className="mb-6 text-sm text-slate-600">
          Upload carrier invoices, WMS shipment export, and your governing rate sheet. Mapping confirmation
          comes next in Track A.
        </p>
        <ol className="mb-8 space-y-2">
          {UPLOAD_STEPS.map((label, i) => (
            <li
              key={label}
              className={`rounded-lg border px-4 py-3 ${i === step ? "border-emerald-600 bg-emerald-50" : "border-slate-200"}`}
            >
              {i + 1}. {label}
            </li>
          ))}
        </ol>
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
          <p className="text-sm text-slate-600">Drop files here (shell — wired to API upload in next slice)</p>
          <input type="file" className="mx-auto mt-4 block text-sm" multiple />
        </div>
        <div className="mt-6 flex justify-between">
          <button
            type="button"
            className="text-sm text-slate-600 disabled:opacity-40"
            disabled={step === 0}
            onClick={() => setStep(step - 1)}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white"
            onClick={() => setStep(Math.min(step + 1, UPLOAD_STEPS.length - 1))}
          >
            {step === UPLOAD_STEPS.length - 1 ? "Done" : "Next step"}
          </button>
        </div>
        <p className="mt-10 text-sm">
          <Link href="/" className="text-emerald-700 underline">
            Home
          </Link>
        </p>
      </main>
    </div>
  );
}
