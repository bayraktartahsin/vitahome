"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";

/**
 * What a family actually opens.
 *
 * Not a dashboard. Today's doses, today's one question, and anything a
 * clinician has been asked to decide — in that order, because that is the order
 * a person at a kitchen table cares about.
 *
 * The check-in question can be played aloud. Audio is synthesised on demand, so
 * a question nobody plays costs nothing, and if speech is unavailable the text
 * is still the thing that was always on screen.
 */

const PID = "p_hero";

type Dose = {
  drug: string;
  amount: string;
  times: string[];
  withFood?: boolean;
  note?: string;
};

type Held = { drug: string; unclear?: string };

type Separation = { drugs: string[]; hoursApart?: number; reason: string };

type CheckIn = { question: string; about: string; answer?: string | null };

type Plan = {
  profile?: { name?: string };
  doseSchedule?: { doses?: Dose[]; unresolved?: Held[]; separations?: Separation[] };
  openCheckIn?: CheckIn;
  openConflicts?: { drug: string; question: string }[];
};

export default function Today() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [answer, setAnswer] = useState("");
  const [sent, setSent] = useState(false);
  const [voice, setVoice] = useState<"idle" | "loading" | "unavailable">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/patient/${PID}/plan`, { cache: "no-store" });
      if (r.ok) setPlan(await r.json());
    } catch {
      /* keep the last good frame */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function play() {
    setVoice("loading");
    try {
      const r = await fetch(`${API}/patient/${PID}/checkin/audio`, { cache: "no-store" });
      if (!r.ok) {
        setVoice("unavailable");
        return;
      }
      const url = URL.createObjectURL(await r.blob());
      const a = audioRef.current ?? new Audio();
      audioRef.current = a;
      a.src = url;
      a.onended = () => URL.revokeObjectURL(url);
      await a.play();
      setVoice("idle");
    } catch {
      setVoice("unavailable");
    }
  }

  async function submit() {
    if (!answer.trim()) return;
    await fetch(`${API}/patient/${PID}/checkin/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer }),
    }).catch(() => {});
    setSent(true);
    setAnswer("");
    load();
  }

  const sched = plan?.doseSchedule;
  const doses = sched?.doses ?? [];
  const held = sched?.unresolved ?? [];
  const q = plan?.openCheckIn;

  // One row per clock time, because that is how a day is actually lived —
  // not one row per drug, which is how a pharmacy thinks.
  const byTime = new Map<string, Dose[]>();
  for (const d of doses) for (const t of d.times ?? []) {
    byTime.set(t, [...(byTime.get(t) ?? []), d]);
  }
  const times = [...byTime.keys()].sort();

  return (
    <main className="theme-family min-h-screen font-sans">
      <header className="border-b border-fam-line px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <Link href="/" className="font-display text-lg text-fam-ink">
            VitaHome
          </Link>
          <span className="text-xs text-fam-ink2">
            {plan?.profile?.name ?? "—"} · day 3
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-2xl px-6 py-8">
        {/* ------------------------------------------------ check-in --- */}
        {q?.question && (
          <section className="rounded-fam border border-fam-accent/30 bg-fam-accentSoft p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-widest text-fam-accent">
                  today&rsquo;s check-in
                </div>
                <p className="mt-2 text-lg leading-snug text-fam-ink">{q.question}</p>
              </div>
              <button
                onClick={play}
                disabled={voice === "loading"}
                aria-label="Read this question aloud"
                className="shrink-0 rounded-full border border-fam-accent/40 bg-fam-surface px-3 py-2 text-sm text-fam-accent transition hover:bg-fam-accent hover:text-white disabled:opacity-50"
              >
                {voice === "loading" ? "…" : "▶︎ listen"}
              </button>
            </div>

            {voice === "unavailable" && (
              <p className="mt-2 text-xs text-fam-ink2">
                Audio isn&rsquo;t available right now — the question is above.
              </p>
            )}

            {q.answer || sent ? (
              <p className="mt-4 text-sm text-fam-ink2">
                Thank you — that&rsquo;s been passed to the care team.
              </p>
            ) : (
              <div className="mt-4 flex gap-2">
                <input
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                  placeholder="Type your answer…"
                  className="flex-1 rounded-fam border border-fam-line bg-fam-surface px-3 py-2 text-sm text-fam-ink outline-none focus:border-fam-accent"
                />
                <button
                  onClick={submit}
                  className="rounded-fam bg-fam-accent px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110"
                >
                  Send
                </button>
              </div>
            )}
          </section>
        )}

        {/* --------------------------------------------------- doses --- */}
        <h1 className="mt-10 font-display text-2xl text-fam-ink">Today</h1>

        {times.length === 0 && (
          <p className="mt-3 text-sm text-fam-ink2">
            No dose schedule yet — run the Pharmacist from the console.
          </p>
        )}

        <div className="mt-4 space-y-3">
          {times.map((t) => (
            <div
              key={t}
              className="rounded-fam border border-fam-line bg-fam-surface p-4 shadow-fam"
            >
              <div className="font-mono text-sm text-fam-accent">{t}</div>
              <ul className="mt-2 space-y-1.5">
                {(byTime.get(t) ?? []).map((d) => (
                  <li key={d.drug} className="text-fam-ink">
                    <span className="font-medium">{d.drug}</span>
                    <span className="text-fam-ink2"> · {d.amount}</span>
                    {d.withFood && (
                      <span className="ml-2 rounded bg-fam-warm/15 px-1.5 py-0.5 text-[10px] text-fam-warm">
                        with food
                      </span>
                    )}
                    {d.note && (
                      <div className="mt-0.5 text-[13px] leading-snug text-fam-ink2">
                        {d.note}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* ------------------------------------------------- separations --- */}
        {(sched?.separations ?? []).length > 0 && (
          <div className="mt-4 rounded-fam border border-fam-warm/30 bg-fam-warm/5 p-4">
            {(sched?.separations ?? []).map((s) => (
              <p key={s.drugs.join()} className="text-sm leading-relaxed text-fam-ink">
                <span className="font-medium">
                  {s.drugs.join(" and ")}
                  {s.hoursApart ? ` — ${s.hoursApart}h apart` : ""}
                </span>
                <span className="text-fam-ink2"> · {s.reason}</span>
              </p>
            ))}
          </div>
        )}

        {/* -------------------------------------------- waiting on a human --- */}
        {held.length > 0 && (
          <section className="mt-8">
            <h2 className="text-sm font-semibold text-fam-ink">
              Waiting on the care team
            </h2>
            <p className="mt-1 text-[13px] leading-relaxed text-fam-ink2">
              We didn&rsquo;t guess at these. A clinician has been asked to decide.
            </p>
            <div className="mt-3 space-y-2">
              {held.map((h) => (
                <div
                  key={h.drug}
                  className="rounded-fam border border-[#9B7BD1]/30 bg-[#9B7BD1]/5 p-4"
                >
                  <div className="font-medium text-fam-ink">{h.drug}</div>
                  <div className="mt-0.5 text-[13px] text-fam-ink2">{h.unclear}</div>
                  <div className="mt-1.5 text-[13px] font-medium text-[#7B5BA8]">
                    Don&rsquo;t take this one until you hear back.
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <footer className="mt-12 border-t border-fam-line pt-5 text-xs leading-relaxed text-fam-ink2">
          VitaHome never diagnoses and never prescribes. It carries out
          instructions a clinician already wrote, and hands anything ambiguous
          back to a person.
        </footer>
      </div>
    </main>
  );
}
