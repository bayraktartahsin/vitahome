"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";
import { TopBar } from "@/lib/ui";

/**
 * The Deconstruction — the demo's opening beat.
 *
 * A discharge summary is a wall of text where the fatal line sits seventh, in
 * the same font as the parking instructions. This screen takes it apart and
 * reassembles it in the order that matters: by what happens if you miss it.
 *
 * The measured latency and model name are always on screen — if a number is
 * going to be said out loud, it should come from the run the audience watched.
 */

type Instruction = {
  id: string;
  lineNo: number;
  text: string;
  type: string;
  criticality: "CRITICAL" | "caution" | "none";
  confidence: number;
  why?: string;
  status: string;
  heldReason?: string | null;
  readings?: string[];
};

type Parsed = {
  documentType: string;
  instructions: Instruction[];
  counts: { total: number; critical: number; heldForHuman: number };
  model: string;
  latencyMs: number;
  lineNumbersExact?: boolean;
};

const TYPE_LABEL: Record<string, string> = {
  medication: "medication",
  medication_stop: "stop taking",
  followup: "appointment",
  restriction: "restriction",
  red_flag: "warning signs",
  other: "instruction",
};

export default function Capture() {
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  async function send(run: () => Promise<Response>) {
    setBusy(true);
    setError(null);
    setParsed(null);
    setRevealed(0);
    setElapsed(0);
    const t0 = performance.now();
    const tick = setInterval(() => setElapsed(performance.now() - t0), 47);
    try {
      const r = await run();
      const body = await r.json();
      if (!r.ok) throw new Error(body?.detail ?? `${r.status}`);
      setParsed(body);
      body.instructions.forEach((_: unknown, i: number) =>
        setTimeout(() => setRevealed(i + 1), 90 + i * 60),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      clearInterval(tick);
      setBusy(false);
    }
  }

  const useSample = () =>
    send(() =>
      fetch(`${API}/demo/seed`, { method: "POST" })
        .then(() => fetch(`${API}/patient/p_hero/plan`))
        .then(async (r) => {
          const plan = await r.json();
          return fetch(`${API}/capture`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              patientId: "p_hero",
              documentText: plan?.carePlan?.sourceDocument,
            }),
          });
        }),
    );

  const onFile = (f: File) => {
    const fd = new FormData();
    fd.append("file", f);
    fd.append("patientId", "p_hero");
    send(() => fetch(`${API}/capture/photo`, { method: "POST", body: fd }));
  };

  return (
    <main className="theme-family min-h-screen font-sans">
      <TopBar
        links={[
          { href: "/today", label: "Today" },
          { href: "/console", label: "Console" },
        ]}
      />

      <div className="mx-auto max-w-3xl px-6 py-12">
        {!parsed && !busy && (
          <>
            <h1 className="font-display text-3xl font-semibold leading-tight text-fam-ink">
              Photograph the discharge papers.
            </h1>
            <p className="mt-3 max-w-xl leading-relaxed text-fam-ink2">
              No typing, no forms. Every instruction on the page comes back with the
              one that matters most at the top — not the one that was printed first.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                onClick={() => fileRef.current?.click()}
                className="rounded-fam bg-fam-accent px-5 py-3 text-sm font-semibold text-fam-bg shadow-sheet transition hover:brightness-110 active:translate-y-px"
              >
                Take a photo
              </button>
              <button
                onClick={useSample}
                className="rounded-fam border border-fam-line bg-fam-surface px-5 py-3 text-sm font-medium text-fam-ink transition hover:bg-fam-surface2"
              >
                Use the sample discharge summary
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
              />
            </div>

            <p className="mt-6 max-w-xl text-[12.5px] leading-relaxed text-fam-ink2">
              Bring your own — a discharge summary, a medication list, a vaccine
              schedule. Where a line can be read two ways it goes to a clinician,
              never to a guess. Hand it something that is not medical and it will
              say so rather than invent instructions.
            </p>
          </>
        )}

        {busy && (
          <div className="py-24 text-center">
            <div className="font-display text-6xl font-semibold tabular-nums text-fam-accent">
              {(elapsed / 1000).toFixed(2)}
              <span className="text-3xl">s</span>
            </div>
            <div className="mt-3 animate-breathe text-sm text-fam-ink2">
              reading the page
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-fam border border-fam-danger/40 bg-fam-danger/5 p-4 text-sm text-fam-danger">
            {error}
          </div>
        )}

        {parsed && (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-3 border-b-2 border-fam-ink pb-3">
              <h1 className="font-display text-2xl font-semibold text-fam-ink">
                {parsed.counts.total} instructions, hardest first
              </h1>
              <span className="font-mono text-[11px] text-fam-ink2">
                {(parsed.latencyMs / 1000).toFixed(2)}s · {parsed.model}
              </span>
            </div>
            <p className="mt-2 text-[13px] text-fam-ink2">
              {parsed.documentType} — re-ordered by what happens if it is missed, not
              by where it appeared on the page.
            </p>

            <ol className="mt-7 space-y-3">
              {parsed.instructions.slice(0, revealed).map((ins) => (
                <Card key={ins.id} ins={ins} exact={parsed.lineNumbersExact !== false} />
              ))}
            </ol>

            {revealed >= parsed.instructions.length && (
              <div className="mt-10 flex flex-wrap items-center gap-4 border-t border-fam-line pt-6">
                <Link
                  href="/console"
                  className="rounded-fam bg-fam-accent px-5 py-3 text-sm font-semibold text-fam-bg shadow-sheet transition hover:brightness-110"
                >
                  Hand it to the fleet
                </Link>
                <span className="font-mono text-[11px] text-fam-ink2">
                  {parsed.counts.critical} critical
                  {parsed.counts.heldForHuman > 0 &&
                    ` · ${parsed.counts.heldForHuman} held for a clinician`}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}

/** Display-only tidy-up — the stored text stays a faithful quote of the page. */
function tidy(text: string) {
  return text
    .replace(/\*+/g, "")
    .replace(/^\s*[-•]\s*/, "")
    .replace(/^\s*\d+\.\s*/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function Card({ ins, exact }: { ins: Instruction; exact: boolean }) {
  const critical = ins.criticality === "CRITICAL";
  const caution = ins.criticality === "caution";
  const held = ins.status === "needs_human";
  const rail = critical ? "#A23B3B" : caution ? "#96731F" : "#DCD3C0";

  return (
    <li
      className="animate-rise rounded-fam border border-fam-line bg-fam-surface shadow-sheet"
      style={{ borderLeft: `3px solid ${rail}` }}
    >
      <div className="flex items-start justify-between gap-4 p-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {critical && (
              <span className="bg-fam-danger px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-fam-bg">
                critical
              </span>
            )}
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-fam-ink2">
              {TYPE_LABEL[ins.type] ?? ins.type}
            </span>
            {held && (
              <span className="border border-fam-hold/40 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em] text-fam-hold">
                held for a clinician
              </span>
            )}
          </div>
          <p
            className={`mt-1.5 leading-snug ${
              critical ? "font-semibold text-fam-ink" : "text-fam-ink"
            }`}
          >
            {tidy(ins.text)}
          </p>
          {ins.why && (
            <p className="mt-2 border-l-2 border-fam-danger/40 pl-3 text-[13.5px] leading-relaxed text-fam-ink2">
              {ins.why}
            </p>
          )}
          {held && ins.heldReason && (
            <p className="mt-2 text-[13px] text-fam-hold">
              {ins.heldReason} — a person decides this, not us.
            </p>
          )}
          {ins.readings && ins.readings.length > 1 && (
            <ul className="mt-2 space-y-1 text-[13px] text-fam-ink2">
              {ins.readings.map((r) => (
                <li key={r}>&mdash; {r}</li>
              ))}
            </ul>
          )}
        </div>
        <span
          className="shrink-0 font-mono text-[11px] text-fam-ink2"
          title={exact ? "line in the source document" : "approximate — counted from the photo"}
        >
          {exact ? "" : "~"}line {ins.lineNo}
        </span>
      </div>
    </li>
  );
}
