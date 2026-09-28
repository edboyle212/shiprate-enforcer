"use client";

import { useEffect, useState } from "react";

export const ORG_SESSION_KEY = "shiprate_demo_org_id";

export function readOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ORG_SESSION_KEY);
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
