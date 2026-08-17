"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";
import { TopBar } from "@/lib/ui";

/**
 * What a family actually opens. Not a dashboard: today's doses by clock time,
 * today's one question, and anything a clinician has been asked to decide — in
 * that order, because that is the order a person at a kitchen table cares.
 */

const PID = "p_hero";

type Dose = { drug: string; amount: string; times: string[]; withFood?: boolean; note?: string };
type Held = { drug: string; unclear?: string };
type Separation = { drugs: string[]; hoursApart?: number; reason: string };
type CheckIn = { question: string; about: string; answer?: string | null };
type Plan = {
  profile?: { name?: string };
  doseSchedule?: { doses?: Dose[]; unresolved?: Held[]; separations?: Separation[] };
  openCheckIn?: CheckIn;
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

  // One row per clock time — how a day is lived, not how a pharmacy files it.
  const byTime = new Map<string, Dose[]>();
  for (const d of doses)
    for (const t of d.times ?? []) byTime.set(t, [...(byTime.get(t) ?? []), d]);
  const times = [...byTime.keys()].sort();

  return (
    <main className="theme-family min-h-screen font-sans">
      <TopBar
        center={`${plan?.profile?.name ?? "—"} · day 3 home`}
        links={[
          { href: "/capture", label: "Photograph" },
          { href: "/console", label: "Console" },
        ]}
      />

      <div className="mx-auto max-w-2xl px-6 py-9">
        {/* -------------------------------------------------- check-in --- */}
        {q?.question && (
          <section
            className="rounded-fam border border-fam-accent/30 bg-fam-accentSoft shadow-sheet"
            style={{ borderLeft: "3px solid #2E6B4E" }}
          >
            <div className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-fam-accent">
                    today&rsquo;s check-in
                  </div>
                  <p className="mt-2 font-display text-[19px] leading-snug text-fam-ink">
                    {q.question}
                  </p>
                </div>
                <button
                  onClick={play}
                  disabled={voice === "loading"}
                  aria-label="Read this question aloud"
                  className="flex shrink-0 items-center gap-1.5 rounded-fam border border-fam-accent/40 bg-fam-surface px-3 py-2 text-[12px] font-medium text-fam-accent transition hover:bg-fam-accent hover:text-fam-bg disabled:opacity-50"
                >
                  {voice === "loading" ? <span className="vh-spin" /> : <PlayGlyph />}
                  listen
                </button>
              </div>

              {voice === "unavailable" && (
                <p className="mt-2 text-[12px] text-fam-ink2">
                  Audio isn&rsquo;t available right now — the question is above.
                </p>
              )}

              {q.answer || sent ? (
                <p className="mt-4 text-[13px] text-fam-ink2">
                  Thank you — that&rsquo;s been passed to the care team.
                </p>
              ) : (
                <div className="mt-4 flex gap-2">
                  <input
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submit()}
                    placeholder="Type your answer"
                    className="flex-1 rounded-fam border border-fam-line bg-fam-surface px-3 py-2 text-sm text-fam-ink outline-none placeholder:text-fam-ink2/60 focus:border-fam-accent"
                  />
                  <button
                    onClick={submit}
                    className="rounded-fam bg-fam-accent px-4 py-2 text-sm font-semibold text-fam-bg transition hover:brightness-110 active:translate-y-px"
                  >
                    Send
                  </button>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ------------------------------------------------------ doses --- */}
        <div className="mt-10 flex items-baseline justify-between border-b-2 border-fam-ink pb-2">
          <h1 className="font-display text-2xl font-semibold text-fam-ink">Today</h1>
          {times.length > 0 && (
            <span className="font-mono text-[11px] text-fam-ink2">
              {doses.length} medications · {times.length} times
            </span>
          )}
        </div>

        {times.length === 0 && (
          <p className="mt-3 text-sm text-fam-ink2">
            No dose schedule yet — run the Pharmacist from the console.
          </p>
        )}

        <div className="mt-4 space-y-3">
          {times.map((t) => (
            <div
              key={t}
              className="rounded-fam border border-fam-line bg-fam-surface p-4 shadow-sheet"
            >
              <div className="font-mono text-[13px] font-semibold text-fam-accent">{t}</div>
              <ul className="mt-2 space-y-2">
                {(byTime.get(t) ?? []).map((d) => (
                  <li key={d.drug} className="leading-snug">
                    <span className="font-medium text-fam-ink">{d.drug}</span>
                    <span className="text-fam-ink2"> · {d.amount}</span>
                    {d.withFood && (
                      <span className="ml-2 border border-fam-warm/40 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-fam-warm">
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

        {(sched?.separations ?? []).length > 0 && (
          <div
            className="mt-4 rounded-fam border border-fam-line bg-fam-surface p-4 shadow-sheet"
            style={{ borderLeft: "3px solid #B85C38" }}
          >
            {(sched?.separations ?? []).map((s) => (
              <p key={s.drugs.join()} className="text-[13.5px] leading-relaxed text-fam-ink">
                <span className="font-medium">
                  {s.drugs.join(" and ")}
                  {s.hoursApart ? ` — ${s.hoursApart}h apart` : ""}
                </span>
                <span className="text-fam-ink2"> · {s.reason}</span>
              </p>
            ))}
          </div>
        )}

        {/* -------------------------------------------- waiting on care --- */}
        {held.length > 0 && (
          <section className="mt-9">
            <h2 className="font-display text-lg font-semibold text-fam-ink">
              Waiting on the care team
            </h2>
            <p className="mt-1 text-[13px] leading-relaxed text-fam-ink2">
              We didn&rsquo;t guess at these. A clinician has been asked to decide.
            </p>
            <div className="mt-3 space-y-2">
              {held.map((h) => (
                <div
                  key={h.drug}
                  className="rounded-fam border border-fam-line bg-fam-surface p-4 shadow-sheet"
                  style={{ borderLeft: "3px solid #4A5A78" }}
                >
                  <div className="font-medium text-fam-ink">{h.drug}</div>
                  <div className="mt-0.5 text-[13px] text-fam-ink2">{h.unclear}</div>
                  <div className="mt-1.5 text-[13px] font-medium text-fam-hold">
                    Don&rsquo;t take this one until you hear back.
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <footer className="mt-12 border-t border-fam-line pt-5 text-[12px] leading-relaxed text-fam-ink2">
          VitaHome never diagnoses and never prescribes. It carries out instructions a
          clinician already wrote, and hands anything ambiguous back to a person.
        </footer>
      </div>
    </main>
  );
}

function PlayGlyph() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
      <path d="M2 1.5v7l6-3.5z" fill="currentColor" />
    </svg>
  );
}
