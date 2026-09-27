import { Suspense } from "react";

import ClientOnboardingInner from "./client-onboarding-inner";

export default function ClientOnboardingPage() {
  return (
    <Suspense fallback={<div className="p-10 text-sm text-slate-500">Loading…</div>}>
      <ClientOnboardingInner />
    </Suspense>
  );
}
