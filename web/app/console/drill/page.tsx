"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";

/**
 * The chaos panel. We hand this to the judge.
 *
 * Recovery here is infrastructure, not choreography: killing a worker leaves the
 * Pub/Sub message unacked, Cloud Run starts a fresh container, and the ledger
 * skips every step that already completed. Nothing is simulated.
 */

const AGENTS = [
  { id: "scheduler",  glyph: "📅", label: "Scheduler",  note: "books appointments · has a live task most often" },
  { id: "reconciler", glyph: "💊", label: "Reconciler", note: "checks medications" },
  { id: "pharmacist", glyph: "🏥", label: "Pharmacist", note: "routes prescriptions" },
  { id: "watchman",   glyph: "👁", label: "Watchman",   note: "monitors red flags" },
  { id: "coach",      glyph: "🗣", label: "Coach",      note: "daily check-ins" },
  { id: "escalator",  glyph: "🚨", label: "Escalator",  note: "pages a human" },
];

type Task = {
  taskId: string; agent: string; status: string; attempt?: number;
  steps?: { name: string; idempotencyKey: string; externalRef?: string }[];
};

export default function Drill() {
  const [patient] = useState("p_hero");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const say = (s: string) =>
    setLog((l) => [`${new Date().toLocaleTimeString()}  ${s}`, ...l].slice(0, 12));

  async function poll() {
    try {
      const r = await fetch(`${API}/patient/${patient}/tasks`, { cache: "no-store" });
      if (r.ok) setTasks((await r.json()).tasks ?? []);
    } catch {}
  }

  useEffect(() => {
    poll();
    const t = setInterval(poll, 2000);
    return () => clearInterval(t);
  }, []);

  async function seedAndDispatch() {
    setBusy("dispatch");
    say("seeding hero patient…");
    await fetch(`${API}/demo/seed`, { method: "POST" }).catch(() => {});
    say("dispatching Scheduler task (cardiology, 7 days)");
    await fetch(`${API}/demo/dispatch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patientId: patient, agent: "scheduler", instructionId: "i_06",
        payload: { specialty: "cardiology", daysOut: 7 },
      }),
    }).catch(() => {});
    say("drill window opens on the FHIR step — kill whenever you like");
    setBusy(null);
  }

  async function kill(agent: string) {
    setBusy(agent);
    say(`💀 killing ${agent} — real process exit, no cleanup`);
    // The process dies mid-request, so this fetch is expected to fail. That's the point.
    await fetch(`${API}/chaos/kill?agent=${agent}&patientId=${patient}`, {
      method: "POST",
    }).catch(() => say("connection dropped — the worker is gone"));
    say("waiting on Pub/Sub redelivery + ledger replay…");
    setBusy(null);
  }

  const live = tasks.filter((t) => t.status === "leased" || t.status === "pending");

  return (
    <main className="theme-console min-h-screen">
      <div className="border-b border-con-line px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between text-xs">
          <Link href="/console" className="text-con-ink2 hover:text-con-ink">← console</Link>
          <div className="font-mono text-con-ink2">chaos panel · failure drill</div>
          <div className="font-mono text-con-ink2">{patient}</div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="text-xl font-semibold">Kill an agent. Any agent. Whenever you like.</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-con-ink2">
          These buttons terminate a real worker process with no cleanup. Recovery is not
          scripted: the Pub/Sub message goes unacked, Cloud Run starts a fresh container,
          and the task ledger skips every step that already completed. The appointment is
          booked exactly once no matter when you pull the trigger.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={seedAndDispatch}
            disabled={busy !== null}
            className="rounded-con bg-con-accent/15 px-4 py-2 text-sm font-semibold text-con-accent ring-1 ring-con-accent/40 transition hover:bg-con-accent/25 disabled:opacity-40"
          >
            ▸ Start a task
          </button>
          <span className="self-center font-mono text-xs text-con-ink2">
            {live.length > 0
              ? `${live.length} task(s) in flight — now kill something`
              : "no task in flight"}
          </span>
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((a) => (
            <button
              key={a.id}
              onClick={() => kill(a.id)}
              disabled={busy !== null}
              className="group rounded-con border border-con-danger/30 bg-con-surface p-4 text-left transition hover:border-con-danger hover:bg-con-danger/10 disabled:opacity-40"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-con-ink">
                  {a.glyph} {a.label}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-widest text-con-danger opacity-60 group-hover:opacity-100">
                  kill
                </span>
              </div>
              <div className="mt-1 text-[11px] text-con-ink2">{a.note}</div>
            </button>
          ))}
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <section>
            <h2 className="font-mono text-xs uppercase tracking-widest text-con-ink2">
              tasks
            </h2>
            <div className="mt-3 space-y-2">
              {tasks.length === 0 && (
                <div className="rounded-con border border-dashed border-con-line p-6 text-center font-mono text-xs text-con-ink2">
                  no tasks yet — press “Start a task”
                </div>
              )}
              {tasks.slice(-6).reverse().map((t) => (
                <div key={t.taskId} className="rounded-con border border-con-line bg-con-surface p-3">
                  <div className="flex items-center justify-between font-mono text-xs">
                    <span className="text-con-ink2">{t.taskId}</span>
                    <StatusChip status={t.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {(t.steps ?? []).map((s) => (
                      <span
                        key={s.name}
                        title={s.idempotencyKey}
                        className="rounded bg-con-accent/15 px-1.5 py-0.5 font-mono text-[10px] text-con-accent"
                      >
                        ✓ {s.name}
                      </span>
                    ))}
                    {(t.steps ?? []).length === 0 && (
                      <span className="font-mono text-[10px] text-con-ink2">no steps yet</span>
                    )}
                  </div>
                  {(t.attempt ?? 1) > 1 && (
                    <div className="mt-2 font-mono text-[10px] text-con-warn">
                      🔁 attempt {t.attempt} — recovered after a worker died
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="font-mono text-xs uppercase tracking-widest text-con-ink2">
              operator log
            </h2>
            <div className="mt-3 rounded-con border border-con-line bg-con-bg p-3 font-mono text-[11px] leading-relaxed">
              {log.length === 0 && <span className="text-con-ink2">—</span>}
              {log.map((l, i) => (
                <div key={i} className="text-con-ink2">
                  {l}
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-con-ink2">
              Full audit trail, including the gap left by the dead worker, is on the
              patient page. The gap is never erased — it is the proof.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}

function StatusChip({ status }: { status: string }) {
  const map: Record<string, string> = {
    done: "text-con-accent bg-con-accent/15",
    leased: "text-con-info bg-con-info/15",
    pending: "text-con-ink2 bg-white/5",
    refused: "text-[#9B7BD1] bg-[#9B7BD1]/15",
    escalated: "text-con-warn bg-con-warn/15",
    failed: "text-con-danger bg-con-danger/15",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${map[status] ?? "text-con-ink2 bg-white/5"}`}>
      {status}
    </span>
  );
}
