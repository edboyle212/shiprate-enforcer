"use client";

import { type FormEvent, useEffect, useState } from "react";

import { ClientShell } from "@/app/components/client-shell";
import {
  TraceApiError,
  confirmTrace,
  getTraceContacts,
  getTraceQueue,
  getTraceRules,
  previewTrace,
  uploadTraceContacts,
  uploadTraceOrders,
  type TraceCarrierContact,
  type TraceClaimPacket,
  type TracePreview,
  type TraceQueueCounts,
  type TraceOrderRow,
  type TraceRules,
} from "@/lib/api";

const EMPTY_COUNTS: TraceQueueCounts = {
  ready_to_review: 0,
  live_investigations: 0,
  awaiting_carrier: 0,
};

const EVIDENCE_LABELS: Record<string, string> = {
  shipment_photo: "Shipment photo",
  sales_invoice: "Sales invoice",
  purchase_invoice: "Purchase invoice",
};

function sampleShipDate() {
  const day = new Date();
  day.setDate(day.getDate() - 7);
  return day.toISOString().slice(0, 10);
}

function downloadText(filename: string, contents: string, type: string) {
  const blob = new Blob([contents], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function statusLabel(status: string | null) {
  if (!status) return "Ready to review";
  if (status === "open" || status === "needs_attention") return "Live investigation";
  if (status === "awaiting_carrier") return "Awaiting carrier";
  if (status === "resolved") return "Resolved";
  return status;
}

function TraceDeskBody({ orgId }: { orgId: string }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [counts, setCounts] = useState<TraceQueueCounts>(EMPTY_COUNTS);
  const [orders, setOrders] = useState<TraceOrderRow[]>([]);
  const [contacts, setContacts] = useState<TraceCarrierContact[]>([]);
  const [rules, setRules] = useState<TraceRules | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [reason, setReason] = useState("loss");
  const [tracking, setTracking] = useState("");
  const [lengthIn, setLengthIn] = useState("");
  const [widthIn, setWidthIn] = useState("");
  const [heightIn, setHeightIn] = useState("");
  const [contents, setContents] = useState("");
  const [orderReference, setOrderReference] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [salesInvoice, setSalesInvoice] = useState<File | null>(null);
  const [purchaseInvoice, setPurchaseInvoice] = useState<File | null>(null);
  const [preview, setPreview] = useState<TracePreview | null>(null);
  const [saved, setSaved] = useState<TraceClaimPacket | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const active = orders.find((order) => order.id === activeId) ?? null;
  const contact = contacts.find((row) => row.carrier_code === active?.carrier_code) ?? null;
  const reasonRules = active && rules ? rules.by_carrier[active.carrier_code]?.[reason] : undefined;
  const requiredEvidence = new Set(reasonRules?.required_evidence ?? []);

  async function refresh(nextQuery = query) {
    setError(null);
    const [queue, contactBook, ruleBook] = await Promise.all([
      getTraceQueue(orgId, nextQuery),
      getTraceContacts(orgId),
      getTraceRules(orgId),
    ]);
    setCounts(queue.counts);
    setOrders(queue.orders);
    setContacts(contactBook.contacts);
    setRules(ruleBook);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refresh("")
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load TraceDesk.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // The queue is loaded for the open organization once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  function openTrace(order: TraceOrderRow) {
    setActiveId(order.id);
    setStep(1);
    setReason("loss");
    setTracking(order.tracking_reference);
    setLengthIn("");
    setWidthIn("");
    setHeightIn("");
    setContents("");
    setOrderReference(order.external_order_id);
    setPhoto(null);
    setSalesInvoice(null);
    setPurchaseInvoice(null);
    setPreview(null);
    setSaved(null);
    setFormError(null);
  }

  function detailPayload(requireContact: boolean, evidence: { kind: string; filename: string }[]) {
    return {
      tracking_reference: tracking,
      reason,
      length_in: Number(lengthIn),
      width_in: Number(widthIn),
      height_in: Number(heightIn),
      contents_summary: contents,
      order_reference: orderReference,
      evidence,
      require_contact: requireContact,
    };
  }

  function evidenceNames() {
    const names: { kind: string; filename: string }[] = [];
    if (photo) names.push({ kind: "shipment_photo", filename: photo.name });
    if (salesInvoice) names.push({ kind: "sales_invoice", filename: salesInvoice.name });
    if (purchaseInvoice) names.push({ kind: "purchase_invoice", filename: purchaseInvoice.name });
    return names;
  }

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await refresh(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function onUploadOrders(file: File) {
    setNotice(null);
    setError(null);
    try {
      const result = await uploadTraceOrders(orgId, file);
      const problems = result.errors.map((row) => `Row ${row.row}: ${row.message}`).join(" ");
      setNotice(`Imported ${result.created} orders. Skipped ${result.skipped} already on the queue. ${problems}`.trim());
      await refresh(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order upload failed.");
    }
  }

  async function onUploadContacts(file: File) {
    setNotice(null);
    setError(null);
    try {
      const result = await uploadTraceContacts(orgId, file);
      const problems = result.errors.map((row) => `Row ${row.row}: ${row.message}`).join(" ");
      setNotice(`Saved ${result.created} contacts and updated ${result.updated}. ${problems}`.trim());
      await refresh(query);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Contact upload failed.");
    }
  }

  async function continueFromDetails() {
    if (!active) return;
    setBusy(true);
    setFormError(null);
    try {
      const next = await previewTrace(orgId, active.id, detailPayload(false, []));
      setPreview(next);
      if (!next.contact_ready && !contact) {
        setFormError(`Upload a ${active.carrier_code} contact before this trace can be saved.`);
      }
      setStep(2);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Check the details and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function continueFromEvidence() {
    if (!active) return;
    setBusy(true);
    setFormError(null);
    try {
      const next = await previewTrace(orgId, active.id, detailPayload(true, evidenceNames()));
      setPreview(next);
      setStep(3);
    } catch (err) {
      setFormError(err instanceof TraceApiError ? err.message : err instanceof Error ? err.message : "Evidence is incomplete.");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!active) return;
    setBusy(true);
    setFormError(null);
    try {
      const result = await confirmTrace(
        orgId,
        active.id,
        {
          tracking_reference: tracking,
          reason,
          length_in: lengthIn,
          width_in: widthIn,
          height_in: heightIn,
          contents_summary: contents,
          order_reference: orderReference,
        },
        { shipment_photo: photo, sales_invoice: salesInvoice, purchase_invoice: purchaseInvoice },
      );
      setSaved(result.packet);
      setNotice("Case saved. The claim packet is stored. Nothing was emailed.");
      await refresh(query);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save the case.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <section className="grid gap-3 sm:grid-cols-3">
        <Count label="Ready to review" value={counts.ready_to_review} />
        <Count label="Live investigations" value={counts.live_investigations} />
        <Count label="Awaiting carrier" value={counts.awaiting_carrier} />
      </section>

      {error ? (
        <p className="mt-4 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-200" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className="mt-4 rounded-lg border border-teal-900 bg-teal-950/40 px-4 py-3 text-sm text-td-ink">{notice}</p> : null}

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <UploadCard
          title="Shipped orders"
          detail="CSV columns: order_id, customer_name, customer_email, carrier, tracking_reference, ship_date."
          onFile={onUploadOrders}
          onSample={() =>
            downloadText(
              "tracedesk-orders.csv",
              `order_id,customer_name,customer_email,carrier,tracking_reference,ship_date\n100245,Ada Lovelace,ada@analytical.example,UPS,1Z999AA10123456784,${sampleShipDate()}\n`,
              "text/csv",
            )
          }
        />
        <UploadCard
          title="Carrier contacts"
          detail="Who this organization wants each carrier's claim addressed to. Columns: carrier, contact_name, email, account_reference."
          onFile={onUploadContacts}
          onSample={() =>
            downloadText(
              "tracedesk-contacts.csv",
              "carrier,contact_name,email,account_reference\nUPS,Avery Chen,avery@northwind.example,ACCT-44\n",
              "text/csv",
            )
          }
        />
      </section>

      <section className="mt-4">
        <h2 className="text-sm font-medium text-slate-300">Contacts on file</h2>
        {contacts.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No carrier contacts uploaded yet. A trace cannot be saved until the order's carrier has one.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {contacts.map((row) => (
              <li key={row.id} className="rounded-lg border border-slate-800 px-3 py-2 text-sm">
                <span className="font-medium">{row.carrier_code}</span>
                <span className="text-slate-400"> · {row.contact_name} · </span>
                <span className="td-mono text-td-ink">{row.email}</span>
                {row.account_reference ? <span className="text-slate-400"> · {row.account_reference}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <form onSubmit={onSearch} className="mt-6 flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="trace-search">
          Search orders
        </label>
        <input
          id="trace-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by order id, customer name, or email"
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded-lg bg-td-accent px-4 py-2 text-sm font-medium text-white">
          Search
        </button>
      </form>

      {loading ? <p className="mt-6 text-sm text-slate-400">Loading the queue…</p> : null}

      {!loading && orders.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-700 px-4 py-8 text-sm text-slate-400">
          No shipped orders {query.trim() ? "match that search" : "yet"}. Upload a CSV to start a trace from an order row.
        </p>
      ) : null}

      <div className="mt-4 space-y-3">
        {orders.map((order) => (
          <article key={order.id} className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="td-mono text-sm text-td-ink">{order.external_order_id}</p>
                <p className="mt-1 text-sm">
                  {order.customer_name}
                  <span className="text-slate-400"> · {order.customer_email}</span>
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {order.carrier_code} · <span className="td-mono">{order.tracking_reference}</span> · shipped {order.ship_date}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs uppercase tracking-wide text-slate-400">{statusLabel(order.case_status)}</span>
                {order.case_id ? null : (
                  <button
                    type="button"
                    onClick={() => openTrace(order)}
                    className="rounded-lg bg-td-accent px-3 py-2 text-sm font-medium text-white"
                  >
                    Raise a trace
                  </button>
                )}
              </div>
            </div>

            {active?.id === order.id ? (
              <div className="mt-4 border-t border-slate-800 pt-4">
                <ol className="mb-4 flex gap-3 text-xs uppercase tracking-wide text-slate-500">
                  <li className={step === 1 ? "text-td-ink" : ""}>1 Details</li>
                  <li className={step === 2 ? "text-td-ink" : ""}>2 Evidence</li>
                  <li className={step === 3 ? "text-td-ink" : ""}>3 Recap</li>
                </ol>
                {formError ? (
                  <p className="mb-3 text-sm text-td-amber" role="alert">
                    {formError}
                  </p>
                ) : null}
                {!contact ? (
                  <p className="mb-3 text-sm text-td-amber">
                    No {order.carrier_code} contact is on file. Upload one above. This trace cannot be saved without it.
                  </p>
                ) : (
                  <p className="mb-3 text-sm text-slate-300">
                    Addressed to {contact.contact_name} <span className="td-mono text-td-ink">&lt;{contact.email}&gt;</span>
                    {contact.account_reference ? ` · ${contact.account_reference}` : ""}. Nothing is emailed.
                  </p>
                )}

                {step === 1 ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Carrier" value={order.carrier_code} readOnly />
                    <Field label="Ship date" value={order.ship_date} readOnly />
                    <label className="text-sm sm:col-span-2">
                      Tracking reference
                      <input
                        value={tracking}
                        onChange={(event) => setTracking(event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 td-mono text-sm"
                      />
                    </label>
                    <label className="text-sm">
                      Reason
                      <select
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                      >
                        <option value="loss">Loss</option>
                        <option value="damage">Damage</option>
                      </select>
                    </label>
                    <label className="text-sm">
                      Order reference
                      <input
                        value={orderReference}
                        onChange={(event) => setOrderReference(event.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                      />
                    </label>
                    <label className="text-sm">
                      Length (in)
                      <input value={lengthIn} onChange={(event) => setLengthIn(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" />
                    </label>
                    <label className="text-sm">
                      Width (in)
                      <input value={widthIn} onChange={(event) => setWidthIn(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" />
                    </label>
                    <label className="text-sm">
                      Height (in)
                      <input value={heightIn} onChange={(event) => setHeightIn(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" />
                    </label>
                    <label className="text-sm sm:col-span-2">
                      Contents
                      <textarea
                        value={contents}
                        onChange={(event) => setContents(event.target.value)}
                        rows={3}
                        className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                      />
                    </label>
                    <div className="sm:col-span-2">
                      <button type="button" disabled={busy} onClick={continueFromDetails} className="rounded-lg bg-td-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                        Continue to evidence
                      </button>
                    </div>
                  </div>
                ) : null}

                {step === 2 ? (
                  <div className="space-y-3">
                    <FileField
                      label={EVIDENCE_LABELS.shipment_photo}
                      required={requiredEvidence.has("shipment_photo")}
                      accept="image/png,image/jpeg,image/webp,image/gif"
                      onChange={setPhoto}
                    />
                    <FileField
                      label={EVIDENCE_LABELS.sales_invoice}
                      required={requiredEvidence.has("sales_invoice")}
                      accept="application/pdf,image/png,image/jpeg,image/webp"
                      onChange={setSalesInvoice}
                    />
                    <FileField
                      label={EVIDENCE_LABELS.purchase_invoice}
                      required={requiredEvidence.has("purchase_invoice")}
                      accept="application/pdf,image/png,image/jpeg,image/webp"
                      onChange={setPurchaseInvoice}
                    />
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setStep(1)} className="rounded-lg border border-slate-700 px-4 py-2 text-sm">
                        Back
                      </button>
                      <button type="button" disabled={busy} onClick={continueFromEvidence} className="rounded-lg bg-td-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
                        Review packet
                      </button>
                    </div>
                  </div>
                ) : null}

                {step === 3 && preview ? (
                  <div className="space-y-3">
                    <dl className="grid gap-2 text-sm sm:grid-cols-2">
                      <div><dt className="text-slate-500">Carrier</dt><dd>{order.carrier_code}</dd></div>
                      <div><dt className="text-slate-500">Reason</dt><dd className="capitalize">{reason}</dd></div>
                      <div><dt className="text-slate-500">Tracking</dt><dd className="td-mono">{preview.normalized_tracking}</dd></div>
                      <div><dt className="text-slate-500">Order</dt><dd>{orderReference}</dd></div>
                      <div><dt className="text-slate-500">Dimensions</dt><dd>{lengthIn} × {widthIn} × {heightIn} in</dd></div>
                      <div><dt className="text-slate-500">Filing deadline</dt><dd>{preview.filing_deadline}</dd></div>
                    </dl>
                    <p className="text-sm">Contents: {contents}</p>
                    <ul className="text-sm text-slate-300">
                      {evidenceNames().map((item) => (
                        <li key={item.kind}>{EVIDENCE_LABELS[item.kind] ?? item.kind}: {item.filename}</li>
                      ))}
                    </ul>
                    {preview.filing_window_uncertain ? (
                      <p className="text-sm text-td-amber">{preview.filing_window_source}</p>
                    ) : (
                      <p className="text-sm text-slate-400">{preview.filing_window_source}</p>
                    )}
                    <div className="rounded-lg border border-slate-700 p-3">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Recipient</p>
                      {preview.recipient ? (
                        <p className="mt-1 text-sm">
                          {preview.recipient.contact_name} <span className="td-mono text-td-ink">&lt;{preview.recipient.email}&gt;</span>
                          {preview.recipient.account_reference ? ` · ${preview.recipient.account_reference}` : ""}
                        </p>
                      ) : (
                        <p className="mt-1 text-sm text-td-amber">No contact uploaded for {order.carrier_code}.</p>
                      )}
                      <p className="mt-2 text-xs text-slate-400">Saving stores the packet. It does not send this email.</p>
                    </div>
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 td-mono text-xs text-slate-200">{preview.email_body}</pre>
                    {saved ? (
                      <div className="flex flex-wrap gap-2">
                        <p className="text-sm text-td-ink">Saved. Email was not sent.</p>
                        <button
                          type="button"
                          className="rounded-lg border border-slate-700 px-4 py-2 text-sm"
                          onClick={() => downloadText(`claim-packet-${saved.id}.json`, JSON.stringify(saved, null, 2), "application/json")}
                        >
                          Download claim packet
                        </button>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <button type="button" onClick={() => setStep(2)} className="rounded-lg border border-slate-700 px-4 py-2 text-sm">
                          Back
                        </button>
                        <button
                          type="button"
                          disabled={busy || !preview.contact_ready}
                          onClick={onConfirm}
                          className="rounded-lg bg-td-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                        >
                          Save case and claim packet
                        </button>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </main>
  );
}

function Count({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-slate-800 px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
    </div>
  );
}

function UploadCard({
  title,
  detail,
  onFile,
  onSample,
}: {
  title: string;
  detail: string;
  onFile: (file: File) => void;
  onSample: () => void;
}) {
  return (
    <div className="rounded-xl border border-slate-800 p-4">
      <h2 className="text-sm font-medium">{title}</h2>
      <p className="mt-1 text-sm text-slate-400">{detail}</p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label={`Upload ${title}`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = "";
          }}
          className="text-sm"
        />
        <button type="button" onClick={onSample} className="text-sm text-td-ink underline">
          Download a sample
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, readOnly }: { label: string; value: string; readOnly?: boolean }) {
  return (
    <label className="text-sm">
      {label}
      <input readOnly={readOnly} value={value} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-300" />
    </label>
  );
}

function FileField({
  label,
  required,
  accept,
  onChange,
}: {
  label: string;
  required: boolean;
  accept: string;
  onChange: (file: File | null) => void;
}) {
  return (
    <label className="block text-sm">
      {label} {required ? <span className="text-td-amber">required</span> : <span className="text-slate-500">optional</span>}
      <input
        type="file"
        accept={accept}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
        className="mt-1 block w-full text-sm"
      />
    </label>
  );
}

export function TraceDeskQueue() {
  return (
    <ClientShell
      title="TraceDesk"
      subtitle="One queue of shipped orders. Raise a trace from the row. Saving stores the claim packet and does not email the carrier."
    >
      {(orgId) => <TraceDeskBody orgId={orgId} />}
    </ClientShell>
  );
}
