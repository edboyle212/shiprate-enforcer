"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import { MoneyComparison } from "@/app/components/ui/money-comparison";
import { StatusPill } from "@/app/components/ui/status-pill";
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
import { formatMoneyMinor } from "@/lib/format-money";

const REVIEW_OPTIONS: { value: "open" | "approved" | "rejected" | "hold"; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "hold", label: "On hold" },
];

function traceRows(trace: Record<string, unknown>) {
  return Object.entries(trace).filter(([, v]) => v != null && v !== "");
}

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
    if (!comment.trim()) {
      setError("Review comment is required.");
      return;
    }
    try {
      const updated = await patchDiscrepancyReview(orgId, id, status, comment.trim());
      setRow(updated);
      setMessage("Review saved.");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    }
  }

  async function onOpenCase() {
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
    try {
      await patchOrgAutonomy(orgId, tier);
      setMessage("Send control saved for this organization.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save autonomy failed");
    }
  }

  async function onNegotiate() {
    if (!dispute) return;
    try {
      await negotiateDisputeCase(orgId, dispute.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage("Negotiation step ran.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Negotiate failed");
    }
  }

  async function onApproveSend() {
    if (!dispute) return;
    try {
      await approveSendDispute(orgId, dispute.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage("Message sent to the logged mailbox.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve send failed");
    }
  }

  async function onSendToCarrier(msg: DisputeMessage) {
    if (!dispute) return;
    try {
      await approveSendDispute(orgId, dispute.id, msg.id);
      const detail = await getDisputeCase(orgId, dispute.id);
      setDispute(detail);
      setMessage(
        platformMail.configured
          ? `Sent from ${platformMail.from_address ?? "your platform address"}.`
          : "Logged as sent (Resend not configured on API).",
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send to carrier failed");
    }
  }

  async function onStop() {
    if (!dispute) return;
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
    if (!dispute) return;
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

  const outboundDraft = dispute?.messages?.find((m) => m.direction === "outbound" && m.status !== "sent");
  const recipient = platformMail.from_address ?? "your configured dispute mailbox";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Link href="/discrepancies" style={{ fontSize: 13, color: "var(--ink-2)" }}>← Back to discrepancies</Link>

      {error && <p style={{ fontSize: 13, color: "var(--danger)" }}>{error}</p>}
      {message && <p style={{ fontSize: 13, color: "var(--pos)" }}>{message}</p>}

      {row && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))",
            gap: 18,
            alignItems: "start",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <h2 className="sr-mono" style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{id}</h2>
              <StatusPill status={row.review_status} />
            </div>

            <section className="sr-panel">
              <MoneyComparison
                billedMinor={row.billed_amount_minor}
                allowedMinor={row.allowed_amount_minor}
                varianceMinor={row.variance_minor}
                currency={row.currency_code}
              />
            </section>

            <section className="sr-panel">
              <h3 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 700 }}>Why this is flagged</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
                {row.reason_codes.map((code) => (
                  <span
                    key={code}
                    style={{
                      fontSize: 12,
                      padding: "4px 10px",
                      borderRadius: 999,
                      background: "var(--attention-bg)",
                      color: "var(--attention)",
                    }}
                  >
                    {code}
                  </span>
                ))}
              </div>
              <p style={{ fontSize: 13, color: "var(--ink-2)", margin: "0 0 12px" }}>
                Billed amount exceeds the rate-card allowance. Calculated from rate card — not AI-rated.
              </p>
              <details>
                <summary style={{ fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Show rating trace</summary>
                <table className="sr-table" style={{ minWidth: 0, marginTop: 12, fontSize: 12 }}>
                  <tbody>
                    {traceRows(row.trace_summary).map(([k, v]) => (
                      <tr key={k}>
                        <td style={{ color: "var(--ink-3)" }}>{k}</td>
                        <td className="sr-mono">{String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </section>

            <section className="sr-panel">
              <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>Review</h3>
              <fieldset style={{ border: "none", margin: 0, padding: 0 }}>
                <legend className="sr-only">Review status</legend>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                  {REVIEW_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "8px 12px",
                        borderRadius: 9,
                        border: "1px solid var(--line)",
                        background: status === opt.value ? "var(--accent-weak)" : "var(--surface)",
                        fontSize: 13,
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="radio"
                        name="review-status"
                        value={opt.value}
                        checked={status === opt.value}
                        onChange={() => setStatus(opt.value)}
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label style={{ display: "block", fontSize: 13, marginBottom: 12 }}>
                Comment <span style={{ color: "var(--danger)" }}>(required)</span>
                <textarea
                  required
                  rows={3}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  style={{
                    display: "block",
                    width: "100%",
                    marginTop: 6,
                    padding: 10,
                    borderRadius: 8,
                    border: "1px solid var(--line)",
                    fontSize: 13,
                  }}
                />
              </label>
              <button type="button" className="sr-btn-primary" onClick={() => void submitReview()}>Save review</button>
            </section>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <section className="sr-panel">
              <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700 }}>Dispute case</h3>
              {!dispute ? (
                <button type="button" className="sr-btn-secondary" onClick={() => void onOpenCase()}>Open dispute case</button>
              ) : (
                <>
                  <p style={{ fontSize: 13, color: "var(--ink-2)" }}>
                    Case {dispute.id.slice(0, 8)}… · Recover{" "}
                    <span className="sr-mono" style={{ fontWeight: 600 }}>
                      {formatMoneyMinor(dispute.claim_amount_minor, dispute.currency_code)}
                    </span>
                  </p>

                  <fieldset style={{ border: "none", margin: "16px 0", padding: 0 }}>
                    <legend style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 8 }}>Set by your company</legend>
                    {(
                      [
                        { value: "draft" as const, label: "Draft only — a person sends every message" },
                        { value: "approve_each" as const, label: "Approve each send" },
                        { value: "autonomous" as const, label: "Higher autonomy until stopped" },
                      ] as const
                    ).map((opt) => (
                      <label key={opt.value} style={{ display: "flex", gap: 8, fontSize: 13, marginBottom: 8 }}>
                        <input
                          type="radio"
                          name="autonomy"
                          checked={tier === opt.value}
                          onChange={() => setTier(opt.value)}
                        />
                        {opt.label}
                      </label>
                    ))}
                    <button type="button" className="sr-btn-secondary" onClick={() => void onSaveTier()}>Save send control</button>
                  </fieldset>

                  {outboundDraft && (
                    <div
                      style={{
                        background: "var(--surface-2)",
                        border: "1px solid var(--line)",
                        borderRadius: 10,
                        padding: 14,
                        marginTop: 12,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                        <StatusPill status="draft" />
                      </div>
                      <p style={{ fontSize: 13, fontWeight: 600, margin: "0 0 8px" }}>{outboundDraft.email_subject}</p>
                      <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", margin: 0, color: "var(--ink-2)" }}>
                        {outboundDraft.email_body}
                      </pre>
                      <div
                        style={{
                          marginTop: 12,
                          padding: 12,
                          background: "var(--info-bg)",
                          borderRadius: 8,
                          fontSize: 12,
                          color: "var(--info)",
                        }}
                      >
                        Recipient: carrier billing contact · Sending account: {recipient}. Nothing is sent until you
                        approve.
                      </div>
                      <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
                        <button type="button" className="sr-btn-primary" onClick={() => void onSendToCarrier(outboundDraft)}>
                          Review &amp; approve send
                        </button>
                        <button type="button" className="sr-btn-secondary">Edit</button>
                      </div>
                    </div>
                  )}

                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
                    <button type="button" className="sr-btn-secondary" onClick={() => void onNegotiate()}>Run agent step</button>
                    {dispute.autonomy_tier !== "draft" && dispute.status === "awaiting_approval" && (
                      <button type="button" className="sr-btn-primary" onClick={() => void onApproveSend()}>Approve send</button>
                    )}
                    <button type="button" className="sr-btn-secondary" onClick={() => void onStop()}>Stop</button>
                  </div>

                  {dispute.status === "awaiting_platform" && (
                    <div style={{ marginTop: 16 }}>
                      <label style={{ fontSize: 13 }}>
                        Record recovered (cents)
                        <input
                          className="sr-mono"
                          value={recovered}
                          onChange={(e) => setRecovered(e.target.value)}
                          placeholder="500"
                          style={{
                            display: "block",
                            width: "100%",
                            marginTop: 6,
                            padding: 8,
                            borderRadius: 8,
                            border: "1px solid var(--line)",
                          }}
                        />
                      </label>
                      <button type="button" className="sr-btn-primary" style={{ marginTop: 10 }} onClick={() => void onRecordCredit()}>
                        Save recovered credit
                      </button>
                    </div>
                  )}
                </>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DiscrepancyDetailPage() {
  const params = useParams();
  const id = String(params.id);
  return (
    <ClientShell title="Discrepancy detail" subtitle="Rate-card comparison and dispute draft.">
      {(orgId) => <DiscrepancyDetailBody orgId={orgId} id={id} />}
    </ClientShell>
  );
}
