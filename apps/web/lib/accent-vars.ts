import type { CSSProperties } from "react";

/** Northstar teal from tokens.css / seed_demo_northstar. */
export const DEFAULT_ACCENT = "#0C757F";

function normalizeHex(hex: string): string {
  const h = hex.trim();
  if (/^#[0-9A-Fa-f]{6}$/.test(h)) return h;
  if (/^#[0-9A-Fa-f]{3}$/.test(h)) {
    const r = h[1];
    const g = h[2];
    const b = h[3];
    return `#${r}${r}${g}${g}${b}${b}`;
  }
  return DEFAULT_ACCENT;
}

/** Partner white-label: only these three vars change per partner. */
export function partnerAccentStyle(primaryColor?: string | null): CSSProperties {
  const accent = normalizeHex(primaryColor ?? DEFAULT_ACCENT);
  return {
    ["--accent" as string]: accent,
    ["--accent-weak" as string]: `${accent}14`,
    ["--accent-ink" as string]: "#FFFFFF",
  };
}
