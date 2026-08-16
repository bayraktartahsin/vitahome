"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";

/**
 * The Deconstruction — the demo's opening beat.
 *
 * A discharge summary is a wall of text where the fatal line sits seventh, in
 * the same font as the parking instructions. This screen takes it apart and
 * puts it back together in the order that matters: by what happens if you miss
 * it. The re-ranking IS the product; everything else here stays out of its way.
 *
 * Two deliberate choices:
 *   - the measured latency and the model name are printed on screen, always.
 *     If we are going to say "three seconds" on camera, the number had better
 *     be coming from the run the audience just watched.
 *   - instructions arrive staggered, not all at once. Fast enough to feel
 *     instant, slow enough that a viewer's eye lands on the red one first.
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
  specialty?: string;
  daysOut?: number;
};

type Parsed = {
  documentType: string;
  instructions: Instruction[];
  counts: { total: number; critical: number; heldForHuman: number };
  model: string;
  latencyMs: number;
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
      // Stagger the reveal so the eye lands on the red one first.
      body.instructions.forEach((_: unknown, i: number) =>
        setTimeout(() => setRevealed(i + 1), 90 + i * 65),
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
      <header className="border-b border-fam-line px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <Link href="/" className="font-display text-lg text-fam-ink">
            VitaHome
          </Link>
          <Link href="/console" className="text-xs text-fam-ink2 hover:text-fam-ink">
            clinician console →
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-10">
        {!parsed && !busy && (
          <>
            <h1 className="font-display text-3xl leading-tight text-fam-ink">
              Photograph the discharge papers.
            </h1>
            <p className="mt-3 max-w-xl leading-relaxed text-fam-ink2">
              No typing, no forms. We read every instruction on the page and put the
              one that matters most at the top — not the one that was printed first.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                onClick={() => fileRef.current?.click()}
                className="rounded-fam bg-fam-accent px-5 py-3 font-semibold text-white shadow-fam transition hover:brightness-110"
              >
                Take a photo
              </button>
              <button
                onClick={useSample}
                className="rounded-fam border border-fam-line bg-fam-surface px-5 py-3 font-semibold text-fam-ink transition hover:bg-fam-surface2"
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

            <p className="mt-6 text-xs leading-relaxed text-fam-ink2">
              Bring your own. A discharge summary, a medication list, a vaccine
              schedule — anything a hospital hands someone and expects them to carry
              out. Where a line can be read two ways, it goes to a clinician rather
              than being guessed at.
            </p>
          </>
        )}

        {busy && (
          <div className="py-20 text-center">
            <div className="font-mono text-5xl tabular-nums text-fam-accent">
              {(elapsed / 1000).toFixed(2)}s
            </div>
            <div className="mt-3 animate-breathe text-sm text-fam-ink2">
              reading the page…
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-fam border border-fam-danger/30 bg-fam-danger/5 p-4 text-sm text-fam-danger">
            {error}
          </div>
        )}

        {parsed && (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h1 className="font-display text-2xl text-fam-ink">
                {parsed.counts.total} instructions, hardest first
              </h1>
              <div className="font-mono text-xs text-fam-ink2">
                {(parsed.latencyMs / 1000).toFixed(2)}s · {parsed.model}
              </div>
            </div>
            <p className="mt-2 text-sm text-fam-ink2">
              {parsed.documentType} · re-ordered by what happens if it is missed,
              not by where it appeared on the page.
            </p>

            <ol className="mt-8 space-y-3">
              {parsed.instructions.slice(0, revealed).map((ins) => (
                <Card key={ins.id} ins={ins} />
              ))}
            </ol>

            {revealed >= parsed.instructions.length && (
              <div className="mt-10 flex flex-wrap items-center gap-4 border-t border-fam-line pt-6">
                <Link
                  href="/console"
                  className="rounded-fam bg-fam-accent px-5 py-3 font-semibold text-white shadow-fam transition hover:brightness-110"
                >
                  Hand it to the fleet
                </Link>
                <span className="text-xs text-fam-ink2">
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

/**
 * Display-only tidy-up. The stored text is a faithful quote of the page,
 * asterisks and list numbering included, because it has to be findable on the
 * paper in your hand. On screen those artefacts just read as broken markdown,
 * so they are stripped here and nowhere else.
 */
function tidy(text: string) {
  return text
    .replace(/\*+/g, "")
    .replace(/^\s*[-•]\s*/, "")
    .replace(/^\s*\d+\.\s*/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function Card({ ins }: { ins: Instruction }) {
  const critical = ins.criticality === "CRITICAL";
  const caution = ins.criticality === "caution";
  const held = ins.status === "needs_human";

  return (
    <li
      className={`animate-lift rounded-fam border bg-fam-surface p-4 ${
        critical
          ? "border-fam-danger/40 ring-1 ring-fam-danger/20"
          : caution
            ? "border-fam-attn/30"
            : "border-fam-line"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {critical && (
              <span className="rounded bg-fam-danger px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
                critical
              </span>
            )}
            <span className="text-[11px] uppercase tracking-wider text-fam-ink2">
              {TYPE_LABEL[ins.type] ?? ins.type}
            </span>
            {held && (
              <span className="rounded bg-[#9B7BD1]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[#9B7BD1]">
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
            <p className="mt-2 border-l-2 border-fam-danger/40 pl-3 text-sm leading-relaxed text-fam-ink2">
              {ins.why}
            </p>
          )}
          {held && ins.heldReason && (
            <p className="mt-2 text-sm text-[#7B5BA8]">
              {ins.heldReason} — a person decides this, not us.
            </p>
          )}
          {ins.readings && ins.readings.length > 1 && (
            <ul className="mt-2 space-y-1 text-sm text-fam-ink2">
              {ins.readings.map((r) => (
                <li key={r}>· {r}</li>
              ))}
            </ul>
          )}
        </div>
        {/* Line number, so any line can be checked against the paper in your hand. */}
        <span className="shrink-0 font-mono text-[11px] text-fam-ink2">
          line {ins.lineNo}
        </span>
      </div>
    </li>
  );
}
