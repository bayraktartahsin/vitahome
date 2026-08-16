"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";

/**
 * The scale view — 3:20 in the demo.
 *
 * Every square is a real fleet: a real FHIR Patient, a real Firestore fleet
 * document, a real care plan. The colour comes from that fleet's own counters,
 * not from a seed value, so clicking one and finding nothing behind it is not
 * a thing that can happen.
 *
 * Sorted by what needs a human, never by arrival. Two hundred patients sorted
 * by arrival is a list; sorted by who is waiting, it is a queue.
 */

type Fleet = {
  id: string;
  name: string;
  condition?: string;
  cohort: boolean;
  waiting: number;
  autonomous: number;
  state: "needs_human" | "active" | "idle";
};

type Payload = {
  fleets: Fleet[];
  count: number;
  needingHuman: number;
  active: number;
};

export default function Fleets() {
  const [data, setData] = useState<Payload | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const poll = useCallback(async () => {
    try {
      const r = await fetch(`${API}/console/fleets?limit=250`, { cache: "no-store" });
      if (r.ok) setData(await r.json());
    } catch {
      /* the grid keeps its last good frame rather than flashing empty */
    }
  }, []);

  useEffect(() => {
    poll();
    const t = setInterval(poll, 2000);
    return () => clearInterval(t);
  }, [poll]);

  async function post(path: string, label: string, msg: string) {
    setBusy(label);
    setNote(msg);
    try {
      const r = await fetch(`${API}${path}`, { method: "POST" });
      const body = await r.json().catch(() => ({}));
      setNote(
        r.ok
          ? `${msg} — ${JSON.stringify(body).slice(0, 120)}`
          : `failed: ${body?.detail ?? r.status}`,
      );
      await poll();
    } finally {
      setBusy(null);
    }
  }

  const fleets = data?.fleets ?? [];

  return (
    <main className="theme-console min-h-screen">
      <div className="border-b border-con-line px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between text-xs">
          <Link href="/console" className="text-con-ink2 hover:text-con-ink">
            ← patient console
          </Link>
          <div className="font-mono text-con-ink2">fleet supervision · all patients</div>
          <Link href="/console/drill" className="text-con-danger hover:underline">
            chaos panel →
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
          <Big value={data?.count} label="fleets" tone="text-con-ink" />
          <Big value={data?.needingHuman} label="need a human" tone="text-con-warn" />
          <Big value={data?.active} label="working" tone="text-con-accent" />
        </div>
        <p className="mt-2 max-w-3xl font-mono text-[10px] leading-relaxed text-con-ink2">
          every square is a real fleet — a FHIR Patient in the Healthcare API, a
          Firestore fleet document, a care plan. state is derived from that
          fleet&rsquo;s own counters. synthetic patients, real infrastructure.
        </p>

        <div className="mt-6 flex flex-wrap gap-2">
          <Btn onClick={() => post("/demo/cohort?count=200", "seed", "seeding 200 fleets")} busy={busy}>
            seed 200 fleets
          </Btn>
          <Btn onClick={() => post("/demo/storm?count=50", "storm", "dispatching 50 real tasks")} busy={busy}>
            hand work to 50
          </Btn>
          <Btn onClick={() => post("/demo/storm?count=200", "storm2", "dispatching 200 real tasks")} busy={busy}>
            hand work to all 200
          </Btn>
          {note && <span className="self-center font-mono text-[10px] text-con-ink2">{note}</span>}
        </div>

        {/* ------------------------------------------------------- grid --- */}
        <div className="mt-8 flex flex-wrap gap-1.5">
          {fleets.length === 0 && (
            <div className="w-full rounded-con border border-dashed border-con-line p-12 text-center font-mono text-xs text-con-ink2">
              no fleets yet — press &ldquo;seed 200 fleets&rdquo;
            </div>
          )}
          {fleets.map((f) => (
            <Square key={f.id} f={f} />
          ))}
        </div>

        {/* -------------------------------------------- queue across all --- */}
        {data && data.needingHuman > 0 && (
          <section className="mt-10">
            <h2 className="font-mono text-xs uppercase tracking-widest text-con-ink2">
              waiting on a person · across every fleet
            </h2>
            <div className="mt-3 space-y-1.5">
              {fleets
                .filter((f) => f.state === "needs_human")
                .map((f) => (
                  <Link
                    key={f.id}
                    href={`/console?patient=${f.id}`}
                    className="flex items-center justify-between rounded-con border border-con-warn/40 bg-con-surface px-4 py-2.5 transition hover:border-con-warn"
                  >
                    <span className="text-sm text-con-ink">{f.name}</span>
                    <span className="font-mono text-[11px] text-con-ink2">
                      {f.condition ?? "—"}
                    </span>
                    <span className="font-mono text-[11px] text-con-warn">
                      {f.waiting} waiting
                    </span>
                  </Link>
                ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function Big({ value, label, tone }: { value?: number; label: string; tone: string }) {
  return (
    <div>
      <span className={`font-mono text-4xl tabular-nums ${tone}`}>{value ?? "—"}</span>
      <span className="ml-2 text-xs text-con-ink2">{label}</span>
    </div>
  );
}

function Btn({
  children,
  onClick,
  busy,
}: {
  children: React.ReactNode;
  onClick: () => void;
  busy: string | null;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy !== null}
      className="rounded-con border border-con-line px-3 py-1.5 font-mono text-[11px] text-con-ink2 transition hover:border-con-accent/50 hover:text-con-ink disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function Square({ f }: { f: Fleet }) {
  const tone = {
    needs_human: "bg-con-warn/80 hover:bg-con-warn",
    active: "bg-con-accent/70 hover:bg-con-accent",
    idle: "bg-con-line hover:bg-con-ink2/50",
  }[f.state];
  return (
    <Link
      href={`/console?patient=${f.id}`}
      title={`${f.name} · ${f.condition ?? "—"} · ${
        f.waiting ? `${f.waiting} waiting on a human` : `${f.autonomous} actions`
      }`}
      className={`h-4 w-4 rounded-[3px] transition ${tone}`}
    />
  );
}
