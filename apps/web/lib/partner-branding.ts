"use client";

import { useEffect, useState } from "react";

import { loadPublicBranding } from "@/lib/api";
import { DEMO_PARTNER_SLUG } from "@/lib/demo-partner";

export type PublicBranding = {
  display_name?: string;
  logo_url?: string;
  primary_color?: string;
};

/** Matches `seed_demo_northstar` branding_json.primary_color when API is unreachable. */
const FALLBACK_ACCENT = "#0f766e";

export function usePartnerBranding(partnerSlug?: string | null) {
  const slug = partnerSlug?.trim() || DEMO_PARTNER_SLUG;
  const [branding, setBranding] = useState<PublicBranding | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadPublicBranding(slug).then((data) => {
      if (!cancelled) setBranding(data);
    });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const accent = branding?.primary_color ?? FALLBACK_ACCENT;
  return { branding, accent, partnerSlug: slug };
}
