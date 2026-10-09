"use client";

import { FormEvent, useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import {
  patchOrganizationProfile,
  getOrganizationProfile,
  type AutonomyTier,
  type OrganizationProfile,
  type ProfilePerson,
} from "@/lib/api";

const ROLES: ProfilePerson["role"][] = ["owner", "admin", "billing", "viewer"];

function AccountBody({ orgId }: { orgId: string }) {
  const [profile, setProfile] = useState<OrganizationProfile | null>(null);
  const [name, setName] = useState("");
  const [contacts, setContacts] = useState({
    primary_name: "",
    primary_email: "",
    billing_email: "",
    disputes_email: "",
  });
  const [carriers, setCarriers] = useState("");
  const [absoluteDollars, setAbsoluteDollars] = useState("5.00");
  const [percent, setPercent] = useState("2");
  const [autonomy, setAutonomy] = useState<AutonomyTier>("draft");
  const [billingEmails, setBillingEmails] = useState<{ carrier: string; email: string }[]>([]);
  const [people, setPeople] = useState<ProfilePerson[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOrganizationProfile(orgId)
      .then((p) => {
        setProfile(p);
        setName(p.name);
        setContacts({
          primary_name: p.contacts.primary_name ?? "",
          primary_email: p.contacts.primary_email ?? "",
          billing_email: p.contacts.billing_email ?? "",
          disputes_email: p.contacts.disputes_email ?? "",
        });
        setCarriers(p.carriers.join(", "));
        setAbsoluteDollars(((p.tolerances.absolute_minor ?? 500) / 100).toFixed(2));
        setPercent(String(p.tolerances.percent ?? 2));
        setAutonomy(p.autonomy_tier);
        const emailRows = Object.entries(p.carrier_billing_emails ?? {}).map(([carrier, email]) => ({
          carrier,
          email,
        }));
        setBillingEmails(emailRows.length ? emailRows : [{ carrier: "", email: "" }]);
        setPeople(p.people.length ? p.people : [{ name: "", email: "", role: "viewer" }]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load profile"));
  }, [orgId]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setStatus(null);
    const emails: Record<string, string> = {};
    for (const row of billingEmails) {
      if (row.carrier.trim() && row.email.trim()) emails[row.carrier.trim()] = row.email.trim();
    }
    try {
      const saved = await patchOrganizationProfile(orgId, {
        name,
        contacts,
        people: people.filter((p) => p.name.trim() || p.email.trim()),
        carriers: carriers
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        tolerances: {
          absolute_minor: Math.round(Number.parseFloat(absoluteDollars || "0") * 100),
          percent: Number.parseFloat(percent || "0"),
        },
        autonomy_tier: autonomy,
        carrier_billing_emails: emails,
      });
      setProfile(saved);
      setStatus("Saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  const feePercent = ((profile?.recovery_fee_bps ?? 2000) / 100).toFixed(2);
  const fieldClass = "mt-1 w-full rounded-lg px-3 py-2 text-sm";
  const fieldStyle = { border: "1px solid var(--line)", background: "var(--surface)" };

  return (
    <main>
      <form onSubmit={(e) => void onSave(e)} className="space-y-8">
        <section className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Company</h2>
          <label className="block text-sm">
            Legal name
            <input
              className="mt-1 w-full rounded-lg px-3 py-2"
              style={{ border: "1px solid var(--line)", background: "var(--surface)" }}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <p className="text-xs" style={{ color: "var(--ink-3)" }}>
            Account slug: <code>{profile?.slug ?? "—"}</code>
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Contacts</h2>
          {(
            [
              ["primary_name", "Primary name"],
              ["primary_email", "Primary email"],
              ["billing_email", "Billing email"],
              ["disputes_email", "Disputes email"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="block text-sm">
              {label}
              <input
                className={fieldClass}
                style={fieldStyle}
                value={contacts[key]}
                onChange={(e) => setContacts({ ...contacts, [key]: e.target.value })}
              />
            </label>
          ))}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Carriers</h2>
          <label className="block text-sm">
            Carriers you bill with (comma-separated)
            <input
              className={fieldClass}
              style={fieldStyle}
              value={carriers}
              onChange={(e) => setCarriers(e.target.value)}
            />
          </label>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Tolerances</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              Absolute (dollars)
              <input
                className={fieldClass}
                style={fieldStyle}
                value={absoluteDollars}
                onChange={(e) => setAbsoluteDollars(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              Percent
              <input
                className={fieldClass}
                style={fieldStyle}
                value={percent}
                onChange={(e) => setPercent(e.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Disputes</h2>
          <label className="block text-sm">
            Autonomy
            <select
              className={fieldClass}
              style={fieldStyle}
              value={autonomy}
              onChange={(e) => setAutonomy(e.target.value as AutonomyTier)}
            >
              <option value="draft">Draft — a person sends every message</option>
              <option value="approve_each">Approve each — a person approves each send</option>
              <option value="autonomous">Autonomous — the agent sends until someone stops it</option>
            </select>
          </label>
          <p className="text-sm" style={{ color: "var(--ink-2)" }}>Carrier billing emails</p>
          {billingEmails.map((row, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-2">
              <input
                className={fieldClass}
                style={fieldStyle}
                placeholder="Carrier"
                value={row.carrier}
                onChange={(e) => {
                  const next = [...billingEmails];
                  next[i] = { ...row, carrier: e.target.value };
                  setBillingEmails(next);
                }}
              />
              <input
                className={fieldClass}
                style={fieldStyle}
                placeholder="billing@carrier.example"
                value={row.email}
                onChange={(e) => {
                  const next = [...billingEmails];
                  next[i] = { ...row, email: e.target.value };
                  setBillingEmails(next);
                }}
              />
            </div>
          ))}
          <button
            type="button"
            className="text-sm sr-link-accent"
            onClick={() => setBillingEmails([...billingEmails, { carrier: "", email: "" }])}
          >
            Add carrier email
          </button>
        </section>

        <section className="space-y-2">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Recovery fee</h2>
          <p className="text-sm" style={{ color: "var(--ink-2)" }}>{feePercent}% of recovered credit. Platform-set. Not editable here.</p>
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>People</h2>
          <p className="text-xs" style={{ color: "var(--ink-3)" }}>Directory only. This is not a login list.</p>
          {people.map((row, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-3">
              <input
                className={fieldClass}
                style={fieldStyle}
                placeholder="Name"
                value={row.name}
                onChange={(e) => {
                  const next = [...people];
                  next[i] = { ...row, name: e.target.value };
                  setPeople(next);
                }}
              />
              <input
                className={fieldClass}
                style={fieldStyle}
                placeholder="Email"
                value={row.email}
                onChange={(e) => {
                  const next = [...people];
                  next[i] = { ...row, email: e.target.value };
                  setPeople(next);
                }}
              />
              <select
                className={fieldClass}
                style={fieldStyle}
                value={row.role}
                onChange={(e) => {
                  const next = [...people];
                  next[i] = { ...row, role: e.target.value as ProfilePerson["role"] };
                  setPeople(next);
                }}
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <button
            type="button"
            className="text-sm sr-link-accent"
            onClick={() => setPeople([...people, { name: "", email: "", role: "viewer" }])}
          >
            Add person
          </button>
        </section>

        {error && <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}
        {status && <p className="text-sm" style={{ color: "var(--pos)" }}>{status}</p>}
        <button type="submit" className="sr-btn-primary">
          Save account
        </button>
      </form>
    </main>
  );
}

export default function AccountPage() {
  return (
    <ClientShell title="Account" subtitle="Company file, contacts, tolerances, and dispute settings.">
      {(orgId) => <AccountBody orgId={orgId} />}
    </ClientShell>
  );
}
