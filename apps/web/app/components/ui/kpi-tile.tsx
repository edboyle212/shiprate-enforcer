import type { CSSProperties } from "react";

export function KpiTile({
  label,
  value,
  sub,
  valueClassName,
  valueStyle,
}: {
  label: string;
  value: string;
  sub?: string;
  valueClassName?: string;
  valueStyle?: CSSProperties;
}) {
  return (
    <div className="sr-kpi">
      <span style={{ fontSize: 12, color: "var(--ink-2)" }}>{label}</span>
      <span
        className={`sr-mono ${valueClassName ?? ""}`}
        style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em", ...valueStyle }}
      >
        {value}
      </span>
      {sub ? <span style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{sub}</span> : null}
    </div>
  );
}
