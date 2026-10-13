"use client";

import { useEffect, useState } from "react";

export const ORG_SESSION_KEY = "shiprate_demo_org_id";

const DEFAULT_DEMO_ORG_ID = process.env.NEXT_PUBLIC_DEFAULT_DEMO_ORG_ID?.trim() || null;

export function readOrgId(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(ORG_SESSION_KEY);
  if (stored) return stored;
  if (DEFAULT_DEMO_ORG_ID) {
    window.localStorage.setItem(ORG_SESSION_KEY, DEFAULT_DEMO_ORG_ID);
    return DEFAULT_DEMO_ORG_ID;
  }
  return null;
}

export function writeOrgId(id: string) {
  window.localStorage.setItem(ORG_SESSION_KEY, id);
}

export function useOrgId() {
  const [orgId, setOrgIdState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setOrgIdState(readOrgId());
    setReady(true);
  }, []);

  function setOrgId(id: string) {
    writeOrgId(id);
    setOrgIdState(id);
  }

  return { orgId, ready, setOrgId };
}
