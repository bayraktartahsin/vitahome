"use client";

import { useState } from "react";
import { API } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { AGENTS, AgentMark, Btn, StatusLine, TopBar, post, useRunner } from "@/lib/ui";

/**
 * The chaos panel. We hand this to the judge.
 *
 * Recovery here is infrastructure, not choreography: killing a worker leaves
 * the Pub/Sub message unacked, Cloud Run starts a fresh container, and the
 * ledger skips every step that already completed. Nothing is simulated.
 */

const KILLABLE = ["scheduler", "reconciler", "pharmacist", "watchman", "coach", "escalator"];

type Task = {
  taskId: string;
  agent: string;
  status: string;
  attempt?: number;
  steps?: { name: string; idempotencyKey: string; externalRef?: string }[];
};

export default function Drill() {
  const [patient] = useState("p_hero");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const { busy, note, run } = useRunner();

  const say = (s: string) =>
    setLog((l) => [`${new Date().toLocaleTimeString()}  ${s}`, ...l].slice(0, 12));

  async function poll() {
    try {
      const r = await fetch(`${API}/patient/${patient}/tasks`, { cache: "no-store" });
      if (r.ok) setTasks((await r.json()).tasks ?? []);
    } catch {
      /* keep last frame */
    }
  }

  usePoll(poll, 2500);

  const start = () =>
    run("start", "seeding and dispatching a Scheduler task", async () => {
      say("seeding the hero patient");
      await post("/demo/seed");
      say("dispatching a Scheduler task — cardiology, 7 days");
      await post("/demo/dispatch", {
        patientId: patient,
        agent: "scheduler",
        instructionId: "i_07",
        payload: { specialty: "cardiology", daysOut: 7 },
      });
      say("task in flight — the armed step will die when it is reached");
    });

  const arm = (agent: string) =>
    run(`arm-${agent}`, `arming ${agent}`, async () => {
      await post(`/chaos/arm?agent=${agent}&patientId=${patient}&step=fhir_appointment`);
      say(`${agent} armed — it will die inside its next step`);
      say("now press Start a task and watch the audit stream");
    });

  const killNow = (agent: string) =>
    run(`kill-${agent}`, `killing ${agent}`, async () => {
      say(`killing ${agent} now — real process exit, no cleanup`);
      // The process dies mid-request; the fetch failing IS the success case.
      await fetch(`${API}/chaos/kill?agent=${agent}&patientId=${patient}`, {
        method: "POST",
      }).catch(() => say("connection dropped — the worker is gone"));
    });

  const live = tasks.filter((t) => t.status === "leased" || t.status === "pending");

  return (
    <main className="theme-console min-h-screen font-sans">
      <TopBar
        dark
        center="chaos panel · the failure drill"
        links={[
          { href: "/console", label: "Console" },
          { href: "/console/fleets", label: "All fleets" },
        ]}
      />

      <div className="mx-auto max-w-6xl px-5 py-8">
        <h1 className="font-display text-2xl font-semibold text-con-ink">
          Kill an agent. Any agent. Whenever you like.
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-con-ink2">
          These buttons terminate a real worker process with no cleanup. Recovery is
          not scripted: the Pub/Sub message goes unacked, Cloud Run starts a fresh
          container, and the ledger skips every step that already completed. The
          appointment is booked exactly once no matter when you pull the trigger.
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Btn dark kind="solid" busy={busy === "start"} onClick={start}>
            Start a task
          </Btn>
          <span className="font-mono text-[11px] text-con-ink2">
            {live.length > 0
              ? `${live.length} task(s) in flight`
              : "no task in flight"}
          </span>
          <StatusLine dark note={note} />
        </div>

        {/* ------------------------------------------------------ roster --- */}
        <section className="mt-8 overflow-hidden rounded-con border border-con-line">
          {KILLABLE.map((id, i) => (
            <div
              key={id}
              className={`flex items-center gap-3 bg-con-panel px-4 py-3 ${
                i > 0 ? "border-t border-con-line" : ""
              }`}
            >
              <AgentMark agent={id} />
              <span className="w-24 text-[13px] font-medium text-con-ink">
                {AGENTS[id].name}
              </span>
              <span className="hidden flex-1 truncate font-mono text-[11px] text-con-ink2 md:block">
                {AGENTS[id].duty}
              </span>
              <div className="ml-auto flex gap-2">
                <Btn dark kind="danger" busy={busy === `arm-${id}`} onClick={() => arm(id)}
                     title="Dies inside its next step — deterministic, still a real crash">
                  arm
                </Btn>
                <Btn dark kind="ghost" busy={busy === `kill-${id}`} onClick={() => killNow(id)}
                     title="Kill immediately — may land on an idle instance">
                  kill now
                </Btn>
              </div>
            </div>
          ))}
        </section>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <section>
            <h2 className="border-b border-con-line pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-con-ink2">
              tasks
            </h2>
            <div className="mt-3 space-y-2">
              {tasks.length === 0 && (
                <div className="rounded-con border border-dashed border-con-line p-6 text-center font-mono text-xs text-con-ink2">
                  no tasks yet — press Start a task
                </div>
              )}
              {tasks.slice(-6).reverse().map((t) => (
                <div key={t.taskId} className="rounded-con border border-con-line bg-con-panel p-3">
                  <div className="flex items-center justify-between font-mono text-[11px]">
                    <span className="text-con-ink2">{t.taskId}</span>
                    <StatusTag status={t.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {(t.steps ?? []).map((s) => (
                      <span
                        key={s.name}
                        title={s.idempotencyKey}
                        className="border border-con-accent/40 bg-con-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-con-accent"
                      >
                        {s.name}
                      </span>
                    ))}
                    {(t.steps ?? []).length === 0 && (
                      <span className="font-mono text-[10px] text-con-ink2">no steps yet</span>
                    )}
                  </div>
                  {(t.attempt ?? 1) > 1 && (
                    <div className="mt-2 font-mono text-[10px] uppercase tracking-wide text-con-warn">
                      attempt {t.attempt} — recovered after a worker died
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="border-b border-con-line pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-con-ink2">
              operator log
            </h2>
            <div className="mt-3 rounded-con border border-con-line bg-con-bg p-3 font-mono text-[11px] leading-relaxed">
              {log.length === 0 && <span className="text-con-ink2">&mdash;</span>}
              {log.map((l, i) => (
                <div key={i} className="text-con-ink2">
                  {l}
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-con-ink2">
              The full audit trail — including the gap the dead worker leaves — is on
              the patient console. The gap is never erased; the scar is the proof.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}

function StatusTag({ status }: { status: string }) {
  const map: Record<string, string> = {
    done: "text-con-accent border-con-accent/40",
    leased: "text-con-info border-con-info/40",
    pending: "text-con-ink2 border-con-line",
    refused: "text-con-hold border-con-hold/40",
    escalated: "text-con-warn border-con-warn/40",
    resolved: "text-con-ink2 border-con-line",
    failed: "text-con-danger border-con-danger/40",
  };
  return (
    <span
      className={`border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${
        map[status] ?? "border-con-line text-con-ink2"
      }`}
    >
      {status}
    </span>
  );
}
