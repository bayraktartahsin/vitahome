"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";

/**
 * Clinician console — dense dark. An ops room.
 *
 * Three panels, in the order a clinician actually needs them:
 *
 *   1. the Autonomy Ledger, because the first honest question about any agent
 *      fleet is "how much of this did it do without a person, and how often did
 *      it stop". Counts only — no invented dollar figures.
 *   2. the exception queue, sorted by SLA pressure rather than arrival. A queue
 *      ordered by arrival lets the urgent thing sit behind the routine one.
 *   3. the audit stream, append-only, including the gaps left by dead workers.
 *      The gap is never cleaned up — in a regulated domain the scar is evidence.
 */

type Ledger = {
  autonomous: number;
  humanDecisions: number;
  refused: number;
  systemsTouched: number;
};

type Exception = {
  taskId: string;
  agent: string;
  kind: "refused" | "escalated";
  question: string;
  options: string[];
  urgency?: string;
  rationale?: string;
  argumentsAgainst?: string;
  hardOverride: boolean;
  deadLetter: boolean;
  waitedSeconds: number;
  slaSeconds: number;
  breached: boolean;
};

type Audit = {
  kind: string;
  actor: string;
  detail: string;
  at?: { seconds?: number } | string;
  taskId?: string;
};

const PID = "p_hero";

export default function Console() {
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [exceptions, setExceptions] = useState<Exception[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const poll = useCallback(async () => {
    const grab = async <T,>(p: string, fb: T): Promise<T> => {
      try {
        const r = await fetch(`${API}${p}`, { cache: "no-store" });
        return r.ok ? await r.json() : fb;
      } catch {
        return fb;
      }
    };
    const [l, e, a] = await Promise.all([
      grab<Ledger | null>(`/patient/${PID}/ledger`, null),
      grab<{ exceptions?: Exception[] }>(`/patient/${PID}/exceptions`, {}),
      grab<{ audit?: Audit[] }>(`/patient/${PID}/audit?limit=60`, {}),
    ]);
    if (l) setLedger(l);
    setExceptions(e.exceptions ?? []);
    setAudit(a.audit ?? []);
  }, []);

  useEffect(() => {
    poll();
    const t = setInterval(poll, 2500);
    return () => clearInterval(t);
  }, [poll]);

  async function post(path: string, body?: unknown, label = "working") {
    setBusy(label);
    try {
      await fetch(`${API}${path}`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      await poll();
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="theme-console min-h-screen">
      <div className="border-b border-con-line px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between text-xs">
          <Link href="/" className="text-con-ink2 hover:text-con-ink">
            ← VitaHome
          </Link>
          <div className="font-mono text-con-ink2">
            clinician console · Robert Hayes · post-PCI day 3
          </div>
          <Link href="/console/drill" className="text-con-danger hover:underline">
            chaos panel →
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* ---------------------------------------------------- ledger --- */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="autonomous actions" value={ledger?.autonomous} tone="accent" />
          <Stat label="human decisions" value={ledger?.humanDecisions} tone="info" />
          <Stat label="refused (ambiguous)" value={ledger?.refused} tone="refuse" />
          <Stat label="external systems touched" value={ledger?.systemsTouched} tone="ink" />
        </div>
        <p className="mt-2 font-mono text-[10px] text-con-ink2">
          verifiable counts only — no estimated savings, no invented dollars
        </p>

        {/* ------------------------------------------------------ runs --- */}
        <div className="mt-6 flex flex-wrap gap-2">
          <Btn onClick={() => post("/demo/seed", undefined, "seed")} busy={busy}>
            seed patient
          </Btn>
          <Btn onClick={() => post(`/demo/book-followups?patientId=${PID}`, undefined, "book")} busy={busy}>
            book every follow-up
          </Btn>
          <Btn
            onClick={() => post("/demo/dispatch", { patientId: PID, agent: "reconciler" }, "recon")}
            busy={busy}
          >
            reconcile medications
          </Btn>
          <Btn onClick={() => post(`/demo/observe?scenario=chest_pain&patientId=${PID}`, undefined, "cp")} busy={busy}>
            report: chest pain
          </Btn>
          <Btn
            onClick={() => post(`/demo/observe?scenario=lightheaded_on_standing&patientId=${PID}`, undefined, "lh")}
            busy={busy}
          >
            report: lightheaded
          </Btn>
          <Btn onClick={() => post(`/demo/reset?patientId=${PID}`, undefined, "reset")} busy={busy} danger>
            reset
          </Btn>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-5">
          {/* ------------------------------------------- exceptions --- */}
          <section className="lg:col-span-3">
            <h2 className="font-mono text-xs uppercase tracking-widest text-con-ink2">
              waiting on a person · {exceptions.length}
            </h2>
            <div className="mt-3 space-y-3">
              {exceptions.length === 0 && (
                <div className="rounded-con border border-dashed border-con-line p-8 text-center font-mono text-xs text-con-ink2">
                  nothing waiting on a human
                </div>
              )}
              {exceptions.map((x) => (
                <ExceptionCard
                  key={x.taskId}
                  x={x}
                  onResolve={() =>
                    post(`/patient/${PID}/task/${x.taskId}/resolve`,
                      { actor: "Dr. Chen", note: "reviewed" }, x.taskId)
                  }
                  onDecide={(option) =>
                    post(`/patient/${PID}/task/${x.taskId}/decide`,
                      { actor: "Dr. Chen", option }, x.taskId)
                  }
                  busy={busy === x.taskId}
                />
              ))}
            </div>
          </section>

          {/* ----------------------------------------------- audit --- */}
          <section className="lg:col-span-2">
            <h2 className="font-mono text-xs uppercase tracking-widest text-con-ink2">
              audit stream · append-only
            </h2>
            <div className="mt-3 max-h-[36rem] space-y-1 overflow-y-auto rounded-con border border-con-line bg-con-bg p-3">
              {audit.length === 0 && (
                <div className="py-8 text-center font-mono text-xs text-con-ink2">—</div>
              )}
              {audit.map((a, i) => (
                <AuditRow key={i} a={a} />
              ))}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ bits -- */

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value?: number;
  tone: "accent" | "info" | "refuse" | "ink";
}) {
  const color = {
    accent: "text-con-accent",
    info: "text-con-info",
    refuse: "text-[#9B7BD1]",
    ink: "text-con-ink",
  }[tone];
  return (
    <div className="rounded-con border border-con-line bg-con-surface p-4">
      <div className={`animate-odometer font-mono text-3xl tabular-nums ${color}`}>
        {value ?? "—"}
      </div>
      <div className="mt-1 text-[11px] leading-tight text-con-ink2">{label}</div>
    </div>
  );
}

function Btn({
  children,
  onClick,
  busy,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  busy: string | null;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy !== null}
      className={`rounded-con border px-3 py-1.5 font-mono text-[11px] transition disabled:opacity-40 ${
        danger
          ? "border-con-danger/30 text-con-danger hover:bg-con-danger/10"
          : "border-con-line text-con-ink2 hover:border-con-accent/50 hover:text-con-ink"
      }`}
    >
      {children}
    </button>
  );
}

function mmss(s: number) {
  const m = Math.floor(s / 60);
  return `${m}m ${String(Math.floor(s % 60)).padStart(2, "0")}s`;
}

function ExceptionCard({
  x,
  onResolve,
  onDecide,
  busy,
}: {
  x: Exception;
  onResolve: () => void;
  onDecide: (option: string) => void;
  busy: boolean;
}) {
  const refusal = x.kind === "refused";
  return (
    <div
      className={`rounded-con border bg-con-surface p-4 ${
        x.breached
          ? "border-con-danger ring-1 ring-con-danger/30"
          : refusal
            ? "border-[#9B7BD1]/40"
            : "border-con-warn/40"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
        <span className={refusal ? "text-[#9B7BD1]" : "text-con-warn"}>
          {refusal ? "⚖ refused" : "🚨 escalated"}
        </span>
        <span className="text-con-ink2">{x.agent}</span>
        {x.urgency && <span className="text-con-ink2">· {x.urgency}</span>}
        {x.hardOverride && (
          <span className="rounded bg-con-danger/20 px-1.5 py-0.5 text-con-danger">
            red-flag override
          </span>
        )}
        {x.deadLetter && (
          <span className="rounded bg-con-danger/20 px-1.5 py-0.5 text-con-danger">
            dead-lettered
          </span>
        )}
        <span className={`ml-auto ${x.breached ? "text-con-danger" : "text-con-ink2"}`}>
          {x.slaSeconds
            ? `${mmss(x.waitedSeconds)} / ${mmss(x.slaSeconds)}${x.breached ? " · BREACHED" : ""}`
            : `waiting ${mmss(x.waitedSeconds)}`}
        </span>
      </div>

      <p className="mt-2 text-sm leading-snug text-con-ink">{x.question}</p>

      {x.rationale && (
        <p className="mt-2 text-xs leading-relaxed text-con-ink2">{x.rationale}</p>
      )}
      {x.argumentsAgainst && (
        <p className="mt-1.5 border-l-2 border-con-line pl-2 text-xs leading-relaxed text-con-ink2">
          <span className="text-con-ink2/70">against: </span>
          {x.argumentsAgainst}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {refusal ? (
          x.options.map((o) => (
            <button
              key={o}
              onClick={() => onDecide(o)}
              disabled={busy}
              className="rounded border border-[#9B7BD1]/40 px-2.5 py-1.5 text-left text-[11px] text-con-ink transition hover:bg-[#9B7BD1]/15 disabled:opacity-40"
            >
              {o}
            </button>
          ))
        ) : (
          <button
            onClick={onResolve}
            disabled={busy}
            className="rounded border border-con-accent/40 px-3 py-1.5 font-mono text-[11px] text-con-accent transition hover:bg-con-accent/15 disabled:opacity-40"
          >
            acknowledge · Dr. Chen
          </button>
        )}
      </div>
    </div>
  );
}

function AuditRow({ a }: { a: Audit }) {
  // The gap left by a killed worker is rendered, not hidden. It is the proof.
  if (a.kind === "AGENT_DOWN") {
    return (
      <div className="animate-gapGrow my-1 rounded border-l-2 border-con-danger bg-con-danger/10 px-2 py-1.5 font-mono text-[11px] text-con-danger">
        💀 {a.detail}
      </div>
    );
  }
  const tone =
    a.kind === "skip"
      ? "text-con-info"
      : a.kind === "redelivery"
        ? "text-con-warn"
        : a.kind === "refusal"
          ? "text-[#9B7BD1]"
          : a.kind === "escalation"
            ? "text-con-danger"
            : "text-con-ink2";
  const glyph =
    { skip: "⏭", redelivery: "🔁", refusal: "⚖", escalation: "🚨", lease: "🔒" }[a.kind] ?? "·";
  return (
    <div className={`font-mono text-[11px] leading-snug ${tone}`}>
      <span className="opacity-60">{glyph}</span>{" "}
      <span className="opacity-50">{a.actor}</span> {a.detail}
    </div>
  );
}
