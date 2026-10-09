export type PillTone = "pos" | "info" | "hold" | "danger";

const LABELS: Record<string, { tone: PillTone; label: string }> = {
  open: { tone: "info", label: "Open" },
  approved: { tone: "pos", label: "Approved" },
  rejected: { tone: "danger", label: "Rejected" },
  hold: { tone: "hold", label: "On hold" },
  suggested: { tone: "hold", label: "Suggested" },
  confirmed: { tone: "pos", label: "Confirmed" },
  uploaded: { tone: "pos", label: "Uploaded" },
  draft: { tone: "hold", label: "Draft — not sent" },
};

export function StatusPill({
  status,
  label,
  tone,
}: {
  status?: string;
  label?: string;
  tone?: PillTone;
}) {
  const key = status?.toLowerCase() ?? "";
  const mapped = LABELS[key];
  const resolvedTone = tone ?? mapped?.tone ?? "info";
  const resolvedLabel = label ?? mapped?.label ?? status ?? "—";
  return (
    <span className={`sr-pill sr-pill--${resolvedTone}`}>
      <span className="sr-pill-dot" aria-hidden />
      {resolvedLabel}
    </span>
  );
}
