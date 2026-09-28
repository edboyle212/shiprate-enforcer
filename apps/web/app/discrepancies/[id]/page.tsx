"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import {
  approveSendDispute,
  getDiscrepancy,
  getDisputeCase,
  getDisputeOutboundMail,
  type DisputeMessage,
  listDisputeCases,
  negotiateDisputeCase,
  openDisputeCase,
  patchDiscrepancyReview,
  patchOrgAutonomy,
  recordDisputeCredit,
  stopDisputeCase,
  type AutonomyTier,
  type DiscrepancyDetail,
  type DisputeCaseDetail,
} from "@/lib/api";

function DiscrepancyDetailBody({ orgId, id }: { orgId: string; id: string }) {
  const [row, setRow] = useState<DiscrepancyDetail | null>(null);
  const [dispute, setDispute] = useState<DisputeCaseDetail | null>(null);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<"open" | "approved" | "rejected" | "hold">("open");
  const [tier, setTier] = useState<AutonomyTier>("draft");
  const [recovered, setRecovered] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [platformMail, setPlatformMail] = useState<{ configured: boolean; from_address: string | null }>({
    configured: false,
    from_address: null,
  });

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load on account and row
  }, [orgId, id]);

  async function loadDisputeFor(discrepancyId: string) {
    const cases = await listDisputeCases(orgId);
    const match = cases.find((c) => c.discrepancy_id === discrepancyId);
    if (!match) {
      setDispute(null);
      return;
    }
    const detail = await getDisputeCase(orgId, match.id);
    setDispute(detail);
    setTier(detail.autonomy_tier);
  }

  async function load() {
    setError(null);
    try {
      const data = await getDiscrepancy(orgId, id);
      setRow(data);
      setStatus(data.review_status as typeof status);
      setComment(data.review_comment ?? "");
      await loadDisputeFor(id);
      try {
        const mail = await getDisputeOutboundMail(orgId);
        setPlatformMail(mail);
      } catch {
        setPlatformMail({ configured: false, from_address: null });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  async function submitReview() {
    if (!orgId || !comment.trim()) {
      setError("Review comment is required.");
      return;
    }
    try {
      const updated = await patchDiscrepancyReview(orgId, id, status, comment.trim());
      setRow(updated);
      setMessage("Review saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    }
  }

  async function onOpenCase() {
    if (!orgId) return;
    try {
      const opened = await openDisputeCase(orgId, id);
      const detail = await getDisputeCase(orgId, opened.id);
      setDispute(detail);
      setTier(detail.autonomy_tier);
      setMessage("Dispute case opened.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Open case failed");
    }
  }

  async function onSaveTier() {
    if (!orgId) return;
    try {
      await patchOrgAutonomy(orgId, tier);
      setMessage("Autonomy level saved for this organization.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save autonomy failed");
    }
  }

  async function onNegotiate() {
    if (!orgId || !dispute) return;
    try {
      await negotiateDisputeCase(orgId, dispute.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage("Negotiation step ran.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Negotiate failed");
    }
  }

  function draftEmailText(msg: DisputeMessage) {
    return `Subject: ${msg.email_subject}\n\n${msg.email_body}`;
  }

  async function onCopyDraft(msg: DisputeMessage) {
    try {
      await navigator.clipboard.writeText(draftEmailText(msg));
      setMessage("Draft copied to clipboard.");
      setError(null);
    } catch {
      setError("Could not copy — select the text and copy manually.");
    }
  }

  async function onSendToCarrier(msg: DisputeMessage) {
    if (!orgId || !dispute) return;
    try {
      await approveSendDispute(orgId, dispute.id, msg.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage(
        platformMail.configured
          ? `Sent from ${platformMail.from_address ?? "your platform address"}. Carrier replies go to your Resend inbox.`
          : "Logged as sent (Resend not configured — set RESEND_API_KEY and DISPUTE_FROM_EMAIL on the API).",
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send to carrier failed");
    }
  }

  async function onApproveSend() {
    if (!orgId || !dispute) return;
    try {
      await approveSendDispute(orgId, dispute.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage("Message sent to the logged mailbox.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve send failed");
    }
  }

  async function onStop() {
    if (!orgId || !dispute) return;
    try {
      await stopDisputeCase(orgId, dispute.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage("Case stopped.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Stop failed");
    }
  }

  async function onRecordCredit() {
    if (!orgId || !dispute) return;
    const amount = Number.parseInt(recovered, 10);
    if (!Number.isFinite(amount)) {
      setError("Enter recovered amount in cents.");
      return;
    }
    try {
      await recordDisputeCredit(orgId, dispute.id, amount);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage("Credit recorded.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Record credit failed");
    }
  }

  function formatMoney(minor: number, currency: string) {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-8 space-y-6">
      {error && <p className="text-sm text-red-400">{error}</p>}
      {message && <p className="text-sm text-emerald-400">{message}</p>}

        {row && (
          <>
            <div className="rounded-xl border border-slate-800 p-5 space-y-2 text-sm">
              <p>
                <span className="text-slate-400">Billed:</span>{" "}
                {formatMoney(row.billed_amount_minor, row.currency_code)}
              </p>
              <p>
                <span className="text-slate-400">Allowed:</span>{" "}
                {formatMoney(row.allowed_amount_minor, row.currency_code)}
              </p>
              <p>
                <span className="text-slate-400">Variance:</span>{" "}
                <span className="text-amber-300">{formatMoney(row.variance_minor, row.currency_code)}</span>
              </p>
              <p>
                <span className="text-slate-400">Reasons:</span> {row.reason_codes.join(", ")}
              </p>
              <p>
                <span className="text-slate-400">Review:</span> {row.review_status}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 p-5">
              <p className="text-sm font-medium mb-2">Rating trace summary</p>
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs">
                {JSON.stringify(row.trace_summary, null, 2)}
              </pre>
            </div>

            <div className="rounded-xl border border-slate-800 p-5 space-y-3">
              <p className="text-sm font-medium">Review workflow</p>
              <select
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={status}
                onChange={(e) => setStatus(e.target.value as typeof status)}
              >
                <option value="open">open</option>
                <option value="approved">approved</option>
                <option value="rejected">rejected</option>
                <option value="hold">hold</option>
              </select>
              <textarea
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                rows={3}
                placeholder="Review comment (required)"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button
                type="button"
                onClick={() => void submitReview()}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium"
              >
                Save review
              </button>
            </div>

            <div className="rounded-xl border border-slate-800 p-5 space-y-3">
              <p className="text-sm font-medium">Client autonomy (upsell)</p>
              <select
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
                value={tier}
                onChange={(e) => setTier(e.target.value as AutonomyTier)}
              >
                <option value="draft">draft — person sends every message</option>
                <option value="approve_each">approve each — person approves each send</option>
                <option value="autonomous">autonomous — agent sends until a stop</option>
              </select>
              <button
                type="button"
                onClick={() => void onSaveTier()}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm"
              >
                Save autonomy
              </button>
            </div>

            <button
              type="button"
              onClick={() => void onOpenCase()}
              className="w-full rounded-lg border border-amber-600 px-4 py-3 text-sm text-amber-200"
            >
              Open dispute case
            </button>

            {dispute && (
              <div className="rounded-xl border border-amber-800 p-5 space-y-4">
                <p className="text-sm font-medium">Dispute case</p>
                <p className="text-sm text-slate-400">
                  Status {dispute.status} · claim {formatMoney(dispute.claim_amount_minor, dispute.currency_code)} ·
                  fee {dispute.fee_bps} bps
                </p>
                {dispute.recovered_amount_minor != null && (
                  <p className="text-sm text-emerald-300">
                    Recovered {formatMoney(dispute.recovered_amount_minor, dispute.currency_code)} · fee{" "}
                    {formatMoney(dispute.fee_amount_minor ?? 0, dispute.currency_code)}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void onNegotiate()}
                    className="rounded-lg bg-amber-700 px-3 py-2 text-sm"
                  >
                    Run agent step
                  </button>
                  {dispute.autonomy_tier !== "draft" && dispute.status === "awaiting_approval" && (
                    <button
                      type="button"
                      onClick={() => void onApproveSend()}
                      className="rounded-lg bg-emerald-700 px-3 py-2 text-sm"
                    >
                      Approve send
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void onStop()}
                    className="rounded-lg border border-slate-600 px-3 py-2 text-sm"
                  >
                    Stop
                  </button>
                </div>
                <div className="space-y-2">
                  {(dispute.messages ?? []).map((msg) => (
                    <div key={msg.id} className="rounded-lg bg-slate-900 p-3 text-xs">
                      <p className="text-slate-400">
                        {msg.direction} · {msg.status} · round {msg.round_number}
                      </p>
                      <p className="mt-1 font-medium">{msg.email_subject}</p>
                      {msg.direction === "outbound" && msg.status !== "sent" && (
                        <div className="mt-2 space-y-2">
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => void onCopyDraft(msg)}
                              className="rounded border border-slate-600 px-2 py-1 text-xs hover:bg-slate-800"
                            >
                              Copy
                            </button>
                            <button
                              type="button"
                              onClick={() => void onSendToCarrier(msg)}
                              className="rounded bg-emerald-700 px-2 py-1 text-xs hover:bg-emerald-600"
                            >
                              Send to carrier
                            </button>
                          </div>
                          <p className="text-slate-500">
                            {platformMail.configured
                              ? `Email goes from ${platformMail.from_address}. You stay in the loop on replies.`
                              : "Resend is not configured on the API yet — Send logs only until you set RESEND_API_KEY and DISPUTE_FROM_EMAIL."}
                          </p>
                        </div>
                      )}
                      <pre className="mt-2 whitespace-pre-wrap">{msg.email_body}</pre>
                    </div>
                  ))}
                </div>
                {dispute.status === "awaiting_platform" && (
                  <div className="space-y-2">
                    <p className="text-sm">Paused for you — enter recovered amount (cents)</p>
                    <input
                      className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm"
                      value={recovered}
                      onChange={(e) => setRecovered(e.target.value)}
                      placeholder="500"
                    />
                    <button
                      type="button"
                      onClick={() => void onRecordCredit()}
                      className="rounded-lg bg-emerald-600 px-4 py-2 text-sm"
                    >
                      Save recovered credit
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
  );
}

export default function DiscrepancyDetailPage() {
  const params = useParams();
  const id = String(params.id);
  return (
    <ClientShell title="Discrepancy detail" subtitle={id}>
      {(orgId) => <DiscrepancyDetailBody orgId={orgId} id={id} />}
    </ClientShell>
  );
}
