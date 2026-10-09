import { formatMoneyMinor } from "@/lib/format-money";

export function MoneyComparison({
  billedMinor,
  allowedMinor,
  varianceMinor,
  currency = "USD",
}: {
  billedMinor: number;
  allowedMinor: number;
  varianceMinor: number;
  currency?: string;
}) {
  const billed = Math.max(billedMinor, 1);
  const allowedPct = Math.min(100, Math.round((allowedMinor / billed) * 100));
  const overPct = Math.min(100 - allowedPct, Math.round((varianceMinor / billed) * 100));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12,
          textAlign: "center",
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>Billed</div>
          <div className="sr-mono" style={{ fontSize: 18, fontWeight: 600 }}>{formatMoneyMinor(billedMinor, currency)}</div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>Allowed</div>
          <div className="sr-mono" style={{ fontSize: 18, fontWeight: 600 }}>{formatMoneyMinor(allowedMinor, currency)}</div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>Variance</div>
          <div className="sr-mono" style={{ fontSize: 18, fontWeight: 700, color: "var(--attention)" }}>
            +{formatMoneyMinor(varianceMinor, currency)}
          </div>
        </div>
      </div>
      <div
        style={{
          height: 11,
          borderRadius: 5,
          background: "var(--line-2)",
          display: "flex",
          overflow: "hidden",
        }}
        role="img"
        aria-label={`Allowed ${allowedPct}%, overcharge ${overPct}%`}
      >
        <span style={{ width: `${allowedPct}%`, background: "var(--accent)", display: "block" }} />
        <span style={{ width: `${overPct}%`, background: "var(--attention)", display: "block" }} />
      </div>
      <p style={{ fontSize: 11, color: "var(--ink-3)", margin: 0 }}>Calculated from rate card</p>
    </div>
  );
}
