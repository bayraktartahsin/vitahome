"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { Btn, StatusLine, TopBar, post, useRunner } from "@/lib/ui";

/**
 * The scale view. Every square is a real fleet — a real FHIR Patient, a real
 * Firestore document, a real care plan — and the color is computed from that
 * fleet's own counters. Clicking one and finding nothing behind it cannot
 * happen, which is the entire point of the screen.
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

type Payload = { fleets: Fleet[]; count: number; needingHuman: number; active: number };

export default function Fleets() {
  const [data, setData] = useState<Payload | null>(null);
  const { busy, note, run } = useRunner();

  const poll = useCallback(async () => {
    try {
      const r = await fetch(`${API}/console/fleets?limit=250`, { cache: "no-store" });
      if (r.ok) setData(await r.json());
    } catch {
      /* keep the last good frame */
    }
  }, []);

  usePoll(poll, 4000);

  const fleets = data?.fleets ?? [];

  return (
    <main className="theme-console min-h-screen font-sans">
      <TopBar
        dark
        center="fleet supervision · all patients"
        links={[
          { href: "/console", label: "Console" },
          { href: "/console/drill", label: "Chaos panel", tone: "danger" },
        ]}
      />

      <div className="mx-auto max-w-7xl px-5 py-8">
        <div className="flex flex-wrap items-baseline gap-x-10 gap-y-2">
          <Big v={data?.count} label="fleets" cls="text-con-ink" />
          <Big v={data?.needingHuman} label="need a human" cls="text-con-warn" />
          <Big v={data?.active} label="working" cls="text-con-accent" />
        </div>
        <p className="mt-2 max-w-3xl font-mono text-[10px] leading-relaxed text-con-ink2">
          every square is a real fleet — a FHIR patient in the Healthcare API, a
          Firestore document, a care plan. state derives from each fleet&rsquo;s own
          counters. synthetic patients, real infrastructure.
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <Btn dark kind="outline" busy={busy === "seed"}
               auto="cohort" onClick={() => run("seed", "seeding 200 fleets", () => post("/demo/cohort?count=200").then(poll))}>
            seed 200 fleets
          </Btn>
          <Btn dark kind="outline" busy={busy === "s50"}
               onClick={() => run("s50", "dispatching 50 real tasks", () => post("/demo/storm?count=50").then(poll))}>
            hand work to 50
          </Btn>
          <Btn dark kind="outline" busy={busy === "s200"}
               onClick={() => run("s200", "dispatching 200 real tasks", () => post("/demo/storm?count=200").then(poll))}>
            hand work to all 200
          </Btn>
        </div>
        <div className="mt-2 min-h-[18px]">
          <StatusLine dark note={note} />
        </div>

        {/* --------------------------------------------------------- grid --- */}
        <div className="mt-7 flex flex-wrap gap-1.5">
          {fleets.length === 0 && (
            <div className="w-full rounded-con border border-dashed border-con-line p-12 text-center font-mono text-xs text-con-ink2">
              no fleets yet — press &ldquo;seed 200 fleets&rdquo;
            </div>
          )}
          {fleets.map((f) => (
            <Square key={f.id} f={f} />
          ))}
        </div>

        <div className="mt-4 flex gap-5 font-mono text-[10px] uppercase tracking-wide text-con-ink2">
          <LegendDot cls="bg-con-line" label="idle" />
          <LegendDot cls="bg-con-accent/70" label="working" />
          <LegendDot cls="bg-con-warn/80" label="needs a human" />
        </div>

        {/* ------------------------------------------------ queue across --- */}
        {data && data.needingHuman > 0 && (
          <section className="mt-10">
            <h2 className="border-b border-con-line pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-con-ink2">
              waiting on a person &middot; across every fleet
            </h2>
            <div className="mt-3 overflow-hidden rounded-con border border-con-line">
              {fleets
                .filter((f) => f.state === "needs_human")
                .map((f, i) => (
                  <Link
                    key={f.id}
                    href={`/console?patient=${f.id}`}
                    className={`flex items-center justify-between gap-4 bg-con-panel px-4 py-2.5 transition hover:bg-con-panel2 ${
                      i > 0 ? "border-t border-con-line" : ""
                    }`}
                  >
                    <span className="text-[13px] text-con-ink">{f.name}</span>
                    <span className="hidden flex-1 truncate font-mono text-[11px] text-con-ink2 sm:block">
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

function Big({ v, label, cls }: { v?: number; label: string; cls: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className={`font-mono text-4xl font-medium ${cls}`}>{v ?? "·"}</span>
      <span className="font-mono text-[11px] uppercase tracking-wide text-con-ink2">
        {label}
      </span>
    </div>
  );
}

function LegendDot({ cls, label }: { cls: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-[2px] ${cls}`} /> {label}
    </span>
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
      className={`h-4 w-4 rounded-[2px] transition ${tone}`}
    />
  );
}
