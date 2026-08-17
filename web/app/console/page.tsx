"use client";

import { useCallback, useEffect, useState } from "react";
import { API } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import {
  AUDIT_TAG,
  AgentMark,
  Btn,
  StatusLine,
  TopBar,
  post,
  useRunner,
} from "@/lib/ui";

/**
 * Clinician console — a ledger, not a wall of cards.
 *
 * Order matters: the Autonomy Ledger first (how much ran alone, how often it
 * stopped), then everything waiting on a person sorted by SLA pressure, then
 * the append-only audit stream with the dead-worker gaps left in.
 */

type Ledger = {
  autonomous: number;
  escalated: number;
  refused: number;
  humanDecisions: number;
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

type Audit = { kind: string; actor: string; detail: string; taskId?: string };

export default function Console() {
  const [PID, setPID] = useState("p_hero");
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [exceptions, setExceptions] = useState<Exception[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [connected, setConnected] = useState(false);
  const { busy, note, run } = useRunner();

  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("patient");
    if (p) setPID(p);
  }, []);

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
    if (l) {
      setLedger(l);
      setConnected(true);
    }
    setExceptions(e.exceptions ?? []);
    setAudit(a.audit ?? []);
  }, [PID]);

  usePoll(poll, 4000);

  const act = (key: string, label: string, path: string, body?: unknown) =>
    run(key, label, () => post(path, body).then(poll));

  return (
    <main className="theme-console min-h-screen font-sans">
      <TopBar
        dark
        center={PID === "p_hero" ? "Robert Hayes · post-PCI · day 3" : PID}
        links={[
          { href: "/console/fleets", label: "All fleets" },
          { href: "/console/drill", label: "Chaos panel", tone: "danger" },
        ]}
      />

      <div className="mx-auto max-w-7xl px-5 py-7">
        {/* ------------------------------------------------------ ledger --- */}
        <section className="grid grid-cols-2 divide-con-line overflow-hidden rounded-con border border-con-line sm:grid-cols-5 sm:divide-x">
          <Stat label="done autonomously" v={ledger?.autonomous} cls="text-con-accent" />
          <Stat label="refused — ambiguous" v={ledger?.refused} cls="text-con-hold" />
          <Stat label="escalated — awaiting" v={ledger?.escalated} cls="text-con-warn" />
          <Stat label="closed by a human" v={ledger?.humanDecisions} cls="text-con-info" />
          <Stat label="systems written" v={ledger?.systemsTouched} cls="text-con-ink" />
        </section>
        <p className="mt-2 font-mono text-[10px] leading-relaxed text-con-ink2">
          verifiable counts only — no estimated savings, no invented dollars.
          {!connected && (
            <span className="ml-2 text-con-warn">
              <span className="vh-spin mr-1" />
              waking the fleet — it sleeps between sessions, first touch takes a second
            </span>
          )}
        </p>

        {/* -------------------------------------------------------- runs --- */}
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <Btn dark kind="outline" busy={busy === "seed"}
               onClick={() => act("seed", "seeding the patient", "/demo/seed")}>
            seed patient
          </Btn>
          <Btn dark kind="outline" busy={busy === "book"}
               onClick={() => act("book", "booking every follow-up", `/demo/book-followups?patientId=${PID}`)}>
            book follow-ups
          </Btn>
          <Btn dark kind="outline" busy={busy === "recon"}
               onClick={() => act("recon", "reconciling medications", "/demo/dispatch",
                 { patientId: PID, agent: "reconciler" })}>
            reconcile medications
          </Btn>
          <Btn dark kind="outline" busy={busy === "pharm"}
               onClick={() => act("pharm", "building the dose schedule", "/demo/dispatch",
                 { patientId: PID, agent: "pharmacist" })}>
            dose schedule
          </Btn>
          <Btn dark kind="outline" busy={busy === "coach"}
               onClick={() => act("coach", "choosing today's question", "/demo/dispatch",
                 { patientId: PID, agent: "coach" })}>
            daily check-in
          </Btn>
          <Btn dark kind="outline" busy={busy === "cp"}
               onClick={() => act("cp", "reporting chest pain", `/demo/observe?scenario=chest_pain&patientId=${PID}`)}>
            report: chest pain
          </Btn>
          <Btn dark kind="outline" busy={busy === "lh"}
               onClick={() => act("lh", "reporting lightheadedness", `/demo/observe?scenario=lightheaded_on_standing&patientId=${PID}`)}>
            report: lightheaded
          </Btn>
          <Btn dark kind="danger" busy={busy === "reset"}
               onClick={() => act("reset", "resetting the demo patient", `/demo/reset?patientId=${PID}`)}>
            reset
          </Btn>
        </div>
        <div className="mt-2 min-h-[18px]">
          <StatusLine dark note={note} />
          {!note && (
            <p className="font-mono text-[10px] text-con-ink2">
              async agents take 15–25s to land — watch the audit stream fill on the right
            </p>
          )}
        </div>

        <div className="mt-7 grid gap-6 lg:grid-cols-5">
          {/* --------------------------------------------- exceptions --- */}
          <section className="lg:col-span-3">
            <h2 className="border-b border-con-line pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-con-ink2">
              waiting on a person &middot; {exceptions.length}
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
                  busy={busy === x.taskId}
                  onResolve={() =>
                    run(x.taskId, "closing as Dr. Chen", () =>
                      post(`/patient/${PID}/task/${x.taskId}/resolve`, {
                        actor: "Dr. Chen",
                        note: "reviewed",
                      }).then(poll))
                  }
                  onDecide={(option) =>
                    run(x.taskId, "recording Dr. Chen's decision", () =>
                      post(`/patient/${PID}/task/${x.taskId}/decide`, {
                        actor: "Dr. Chen",
                        option,
                      }).then(poll))
                  }
                />
              ))}
            </div>
          </section>

          {/* ------------------------------------------------- audit --- */}
          <section className="lg:col-span-2">
            <h2 className="border-b border-con-line pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-con-ink2">
              audit stream &middot; append-only
            </h2>
            <div className="mt-3 max-h-[38rem] space-y-[3px] overflow-y-auto pr-1">
              {audit.length === 0 && (
                <div className="py-8 text-center font-mono text-xs text-con-ink2">
                  &mdash;
                </div>
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

/* ---------------------------------------------------------------- pieces -- */

function Stat({ label, v, cls }: { label: string; v?: number; cls: string }) {
  return (
    <div className="bg-con-panel px-4 py-3.5">
      <div className={`animate-odometer font-mono text-[26px] font-medium leading-none ${cls}`}>
        {v ?? "·"}
      </div>
      <div className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-con-ink2">
        {label}
      </div>
    </div>
  );
}

function mmss(s: number) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

function ExceptionCard({
  x,
  busy,
  onResolve,
  onDecide,
}: {
  x: Exception;
  busy: boolean;
  onResolve: () => void;
  onDecide: (option: string) => void;
}) {
  const refusal = x.kind === "refused";
  const edge = x.breached ? "#C9604F" : refusal ? "#8FA3CC" : "#D2A03C";
  const slaPct = x.slaSeconds ? Math.min(100, (x.waitedSeconds / x.slaSeconds) * 100) : 0;

  return (
    <div
      className="rounded-con border border-con-line bg-con-panel"
      style={{ borderLeft: `3px solid ${edge}` }}
    >
      <div className="p-4">
        <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-[0.12em]">
          <span className={refusal ? "text-con-hold" : "text-con-warn"}>
            {refusal ? "refused" : "escalated"}
          </span>
          <AgentMark agent={x.agent} size={16} />
          <span className="text-con-ink2">{x.agent}</span>
          {x.urgency && <span className="text-con-danger">{x.urgency}</span>}
          {x.hardOverride && (
            <span className="bg-con-danger/20 px-1.5 py-0.5 text-con-danger">
              red-flag override
            </span>
          )}
          {x.deadLetter && (
            <span className="bg-con-danger/20 px-1.5 py-0.5 text-con-danger">
              dead-lettered
            </span>
          )}
          <span className={`ml-auto ${x.breached ? "text-con-danger" : "text-con-ink2"}`}>
            {x.slaSeconds
              ? `${mmss(x.waitedSeconds)} / ${mmss(x.slaSeconds)}${x.breached ? " — breached" : ""}`
              : `waiting ${mmss(x.waitedSeconds)}`}
          </span>
        </div>

        {x.slaSeconds > 0 && (
          <div className="mt-2 h-[3px] w-full overflow-hidden rounded bg-con-line">
            <div
              className="h-full transition-[width] duration-1000"
              style={{
                width: `${slaPct}%`,
                background: x.breached ? "#C9604F" : "#D2A03C",
              }}
            />
          </div>
        )}

        <p className="mt-2.5 text-[13.5px] leading-snug text-con-ink">{x.question}</p>

        {x.rationale && (
          <p className="mt-2 text-[12px] leading-relaxed text-con-ink2">{x.rationale}</p>
        )}
        {x.argumentsAgainst && (
          <p className="mt-1.5 border-l-2 border-con-line pl-2 text-[12px] leading-relaxed text-con-ink2">
            <span className="opacity-60">against — </span>
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
                className="rounded-con border border-con-hold/40 px-2.5 py-1.5 text-left text-[12px] leading-snug text-con-ink transition hover:bg-con-hold/15 disabled:opacity-45"
              >
                {busy && <span className="vh-spin mr-1.5" />}
                {o}
              </button>
            ))
          ) : (
            <Btn dark kind="outline" busy={busy} onClick={onResolve}>
              acknowledge · Dr. Chen
            </Btn>
          )}
        </div>
      </div>
    </div>
  );
}

function AuditRow({ a }: { a: Audit }) {
  // The gap left by a killed worker is rendered, never hidden. It is the proof.
  if (a.kind === "AGENT_DOWN") {
    return (
      <div className="animate-gapGrow my-1.5 border-l-2 border-con-danger bg-con-danger/10 px-2.5 py-2 font-mono text-[11px] leading-snug text-con-danger">
        <span className="mr-2 font-semibold uppercase tracking-wider">down</span>
        {a.detail}
      </div>
    );
  }
  const t = AUDIT_TAG[a.kind] ?? { tag: a.kind.slice(0, 5), cls: "text-con-ink2" };
  return (
    <div className="flex gap-2 font-mono text-[11px] leading-snug">
      <span className={`w-12 shrink-0 text-right uppercase ${t.cls}`}>{t.tag}</span>
      <span className="text-con-ink2">
        <span className="opacity-55">{a.actor}</span> {a.detail}
      </span>
    </div>
  );
}
