"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { createPartnerAccount, listPartnerAccounts, type PartnerAccountRow } from "@/lib/api";
import { writeOrgId } from "@/lib/session";

export default function PartnerAccountsPage() {
  const params = useParams<{ partnerId: string }>();
  const router = useRouter();
  const partnerId = params.partnerId;
  const [rows, setRows] = useState<PartnerAccountRow[]>([]);
  const [query, setQuery] = useState("");
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      setRows(await listPartnerAccounts(partnerId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load accounts");
    }
  }

  useEffect(() => {
    void refresh();
  }, [partnerId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) => row.name.toLowerCase().includes(q) || row.slug.toLowerCase().includes(q));
  }, [rows, query]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await createPartnerAccount(partnerId, newName.trim());
      setNewName("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  function openAccount(id: string) {
    writeOrgId(id);
    router.push("/dashboard");
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-4">
        <p className="text-sm text-slate-400">Partner admin</p>
        <h1 className="text-2xl font-semibold">Accounts — {partnerId}</h1>
        <p className="mt-2 text-sm">
          <Link href={`/partner/${partnerId}/onboarding`} className="text-emerald-400 hover:underline">
            Partner setup
          </Link>
          {" · "}
          <Link href="/" className="text-slate-400 hover:underline">
            Home
          </Link>
        </p>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-8 space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="Search by name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <form onSubmit={(e) => void onCreate(e)} className="flex flex-col gap-3 sm:flex-row">
          <input
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="New account legal name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button type="submit" className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium">
            New account
          </button>
        </form>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Slug</th>
                <th className="px-4 py-3">Setup</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Invite</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const invite = `/p/${partnerId}/onboarding?org=${row.id}`;
                return (
                  <tr key={row.id} className="border-t border-slate-800">
                    <td className="px-4 py-3">{row.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{row.slug}</td>
                    <td className="px-4 py-3">{row.setup_complete ? "Complete" : "Unfinished"}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{row.created_at ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Link href={invite} className="text-emerald-400 hover:underline">
                        Invite
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        className="rounded-md border border-slate-600 px-3 py-1 text-xs"
                        onClick={() => openAccount(row.id)}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="px-4 py-6 text-sm text-slate-500">No accounts yet.</p>}
        </div>
      </main>
    </div>
  );
}
