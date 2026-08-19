"use client";

import { useCallback, useEffect, useState } from "react";
import { API } from "@/lib/api";
import { Btn, StatusLine, TopBar, post, useRunner } from "@/lib/ui";

/**
 * The Director — a teleprompter for recording the demo.
 *
 * Two windows: THIS one on a screen the camera does not see, and a second
 * browser window (the "stage") that gets recorded. The Director shows one cue
 * at a time in type large enough to read from across a desk:
 *
 *   SAY   — read it out loud, exactly as written
 *   CLICK — do this one thing on the stage window
 *   WAIT  — say nothing; the silence is the evidence
 *
 * Advance with the right-arrow key or the Next button. Nothing here appears in
 * the recording, and nothing here talks to the fleet mid-take — the stage is
 * driven by you, on camera, which is the whole point of an unedited demo.
 */

type Cue = {
  kind: "say" | "click" | "wait" | "stage";
  text: string;
  sub?: string;
  stage?: string;
};

const STAGE = "https://vitahome.vitamedas.com";

const CUES: Cue[] = [
  { kind: "stage", text: "Stage window: open /capture", stage: "/capture",
    sub: "hold the printed discharge summary in your hand · press → when recording has started" },

  { kind: "say", text: "This is a discharge summary. A dozen instructions on it. At least one of them kills him if it gets missed." },
  { kind: "say", text: "Find it. You have ten seconds." },
  { kind: "wait", text: "Hold the paper up. Count 10 silently.", sub: "actually count — one one-thousand, two one-thousand…" },
  { kind: "say", text: "It took me three readings." },
  { kind: "say", text: "If you have ever stood in a hospital corridor holding your parent's paperwork, you know this feeling. I was in another country when my family got this one.",
    sub: "flat voice · say it once · never repeat it" },

  { kind: "say", text: "So I photograph it. No typing, no forms, no chat window. The document is the interface." },
  { kind: "click", text: "Click: “Use the sample discharge summary”", sub: "then SAY NOTHING until the list finishes appearing" },
  { kind: "say", text: "Read the timer from the screen: “___ seconds.”", sub: "say whatever number is actually shown" },
  { kind: "say", text: "Top of the list, in red — do not stop ticagrelor. That is the one. Stopping a blood thinner early after a stent is how people die in the month after they go home feeling fine." },
  { kind: "say", text: "On the paper it is seventh, in the same font as “no lifting over ten pounds”. It is first here because it is fatal. The fleet re-ranks the page by consequence." },
  { kind: "say", text: "And the sentence underneath it is not on the document. That is the fleet explaining to a frightened family member what actually happens." },

  { kind: "stage", text: "Stage window: open /console", stage: "/console" },
  { kind: "say", text: "Now the part nobody does. Somebody has to carry those instructions out. That is usually a daughter with a full-time job and a phone tree." },
  { kind: "say", text: "Watch the counters — and watch my phone." },
  { kind: "click", text: "Click: “book follow-ups”  ·  then click: “reconcile medications”", sub: "two clicks, then SAY NOTHING ~20s — watch the audit stream fill" },
  { kind: "wait", text: "Silence until “refused” shows 1 and the purple card appears.", sub: "~20–30 seconds. Do not fill the silence." },
  { kind: "click", text: "Pick up the phone. Open Google Calendar. Pull down to refresh. Turn the screen to the camera.", sub: "the bookings are there" },
  { kind: "say", text: "Real appointments, in my actual phone's calendar. Not a screenshot — the fleet owns a calendar, it is shared to my account, and it writes through the Calendar API with the same idempotency keys as the clinical record." },
  { kind: "say", text: "Remember this phone. When I kill the Scheduler in a minute — one event. Never two." },

  { kind: "say", text: "And then it stops. One instruction on this sheet is genuinely ambiguous. Watch what it did with it." },
  { kind: "say", text: "It refused. It did not guess. It assembled both readings — there they are, each citing the line it came from — and put a licensed human in front of the decision." },
  { kind: "say", text: "That is the counter: refused, one. I put that number next to “done autonomously” on purpose. Everyone here is optimising for how much their agents do alone. In medicine that is the wrong axis." },

  { kind: "click", text: "Click: “dose schedule”  ·  wait ~20s  ·  then click: “daily check-in”  ·  wait ~20s", sub: "watch the audit stream while you wait — you can talk over this one" },
  { kind: "say", text: "A refusal is only worth something if the rest of the fleet respects it." },
  { kind: "stage", text: "Stage window: open /today", stage: "/today" },
  { kind: "say", text: "The Pharmacist built the day — real clock times. And amlodipine is held. Not dropped — held, at the bottom: “don't take this one until you hear back.” Scheduling a disputed drug would be a clinical decision made silently by the agent least qualified to make it." },
  { kind: "say", text: "And the Coach gets one question a day. Read it from the screen: “___”. It chose the question whose answer would help the clinician settle the open decision. Nobody wired these three agents together.", sub: "optionally press ▶ listen — the fleet asks out loud" },

  { kind: "stage", text: "Stage window: open /console/drill", stage: "/console/drill" },
  { kind: "say", text: "Everything so far was the happy path. Let me break it. This panel kills a real worker process — no cleanup, no graceful shutdown. And the Scheduler no longer even runs on this service — it runs on its own." },
  { kind: "click", text: "Click: “arm” on the Scheduler row  ·  then click: “Start a task”", sub: "then open /console in the stage window and SAY NOTHING" },
  { kind: "stage", text: "Stage window: open /console — watch the audit stream", stage: "/console" },
  { kind: "wait", text: "Silence ~25s. Watch for: DOWN (red) → REDO → a NEW worker id → SKIP.", sub: "the silence is the evidence — hold it" },
  { kind: "say", text: "The process is gone. Nothing caught that. The message was never acknowledged, so Pub/Sub redelivered it, Cloud Run supplied a fresh container — look at the worker id, different process — and the step it had already finished says SKIP. Skipped, not repeated." },
  { kind: "click", text: "Pick up the phone again. Refresh the calendar. Show the camera.", sub: "one event for today's booking — not two" },
  { kind: "say", text: "One appointment in the clinical record. One event on the phone. Never two of either — the idempotency key is written into both external systems. At-least-once delivery plus idempotent steps is effectively-once. There is no exactly-once, and I am not going to claim there is." },
  { kind: "say", text: "And the red gap stays in the audit trail permanently. In a regulated domain, the scar is the evidence." },

  { kind: "say", text: "Monitoring has been armed since minute one — against the red flags printed on this document. Here is a message from his daughter." },
  { kind: "click", text: "Click: “report: chest pain”  ·  then SAY NOTHING ~25s", sub: "an amber ESCALATED card appears with a 5:00 clock counting" },
  { kind: "say", text: "Paged. Note what it did not do — it did not treat, did not advise, did not reassure her. It put a clinician on it and started a five-minute clock. And that card is the one kind of task no agent can close." },
  { kind: "click", text: "Click: “acknowledge · Dr. Chen” on the escalation card", sub: "watch “closed by a human” go to 1" },
  { kind: "say", text: "Now the harder one." },
  { kind: "click", text: "Click: “report: lightheaded”  ·  then SAY NOTHING ~25s", sub: "NOTHING appears in the queue — read the audit stream instead" },
  { kind: "say", text: "It decided a human was not needed — and wrote down its reason, the strongest argument against its own decision, and what would have changed its answer. Anything can be built to panic. Restraint is the expensive part — a monitor that escalates everything is ignored inside a week." },

  { kind: "stage", text: "Stage window: open /console/fleets", stage: "/console/fleets" },
  { kind: "say", text: "One patient is a demo. Two hundred coloured squares is the easiest thing in the world to fake — so let me hand all two hundred of them real work." },
  { kind: "click", text: "Click: “hand work to all 200”  ·  then SAY NOTHING while the grid turns green", sub: "~30s · the page stays responsive the whole time" },
  { kind: "say", text: "Every square is a real patient record in the Healthcare API. Click any of them and the fleet behind it is there. The patients are synthetic. The infrastructure is not." },
  { kind: "say", text: "And nothing about this is cardiac-specific. Wherever a human being is handed a piece of paper and expected to execute it correctly for six weeks — this works." },

  { kind: "click", text: "Put the paper back in frame. Hold it up.", sub: "same framing as the opening" },
  { kind: "say", text: "The hospital saves your life. Then it hands you a piece of paper." },
  { kind: "say", text: "We take it from there." },
  { kind: "wait", text: "Stop talking. Hold for 3 seconds. Stop the recording.", sub: "end on silence, not on a thank-you" },
];

export default function Director() {
  const [i, setI] = useState(0);
  const [started, setStarted] = useState(false);
  const { busy, note, run } = useRunner();

  const next = useCallback(() => setI((v) => Math.min(v + 1, CUES.length - 1)), []);
  const back = useCallback(() => setI((v) => Math.max(v - 1, 0)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); next(); }
      if (e.key === "ArrowLeft") { e.preventDefault(); back(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, back]);

  const cue = CUES[i];
  const stageNow = [...CUES.slice(0, i + 1)].reverse().find((c) => c.stage)?.stage ?? "/capture";

  const tone = {
    say: "text-con-ink",
    click: "text-con-warn",
    wait: "text-con-accent",
    stage: "text-con-info",
  }[cue.kind];
  const label = { say: "SAY", click: "DO", wait: "SILENCE", stage: "STAGE" }[cue.kind];

  return (
    <main className="theme-console flex min-h-screen flex-col font-sans">
      <TopBar dark center="director · teleprompter — this window is NOT recorded"
        links={[{ href: "/console", label: "Console" }]} />

      {!started && (
        <div className="mx-auto w-full max-w-3xl px-6 py-10">
          <h1 className="font-display text-2xl font-semibold text-con-ink">
            Before the take
          </h1>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-[14px] leading-relaxed text-con-ink2">
            <li>Open a <b className="text-con-ink">second browser window</b> — that one gets recorded. Put THIS window where the recording cannot see it (second screen, or your phone).</li>
            <li>In the second window open <span className="font-mono text-con-info">{STAGE}/capture</span> and zoom to 125% (Cmd and +).</li>
            <li>Press the two buttons below, in order, and wait for each to say done.</li>
            <li>Phone on the desk: Google Calendar app open, signed into the shared account.</li>
            <li>Start the screen recording of the second window, then press <b className="text-con-ink">Start</b>.</li>
          </ol>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Btn dark kind="outline" busy={busy === "reset"}
              onClick={() => run("reset", "wiping rehearsal data", () => post("/demo/reset?patientId=p_hero"))}>
              1 · reset the demo patient
            </Btn>
            <Btn dark kind="outline" busy={busy === "seed"}
              onClick={() => run("seed", "seeding Robert Hayes", () => post("/demo/seed"))}>
              2 · seed the patient
            </Btn>
            <Btn dark kind="solid" onClick={() => setStarted(true)}>
              Start &rarr;
            </Btn>
          </div>
          <div className="mt-2 min-h-[18px]"><StatusLine dark note={note} /></div>
          <p className="mt-6 font-mono text-[11px] leading-relaxed text-con-ink2">
            during the take: RIGHT ARROW or SPACE = next cue · LEFT = back.<br />
            SAY = read aloud exactly · DO = one action on the stage window · SILENCE = say nothing, let it land.
          </p>
        </div>
      )}

      {started && (
        <div className="flex flex-1 flex-col">
          <div className="flex items-center justify-between border-b border-con-line px-6 py-2 font-mono text-[11px] text-con-ink2">
            <span>cue {i + 1} / {CUES.length}</span>
            <span className="text-con-info">stage should show: {stageNow}</span>
            <span>&larr; back · &rarr; next</span>
          </div>

          <div className="flex flex-1 flex-col items-center justify-center px-8 py-10 text-center">
            <div className={`mb-6 font-mono text-[13px] uppercase tracking-[0.3em] ${tone}`}>
              {label}
            </div>
            <div
              className={`max-w-4xl ${
                cue.kind === "say"
                  ? "font-display text-[2.1rem] font-semibold leading-snug md:text-[2.6rem]"
                  : "font-mono text-[1.7rem] leading-snug md:text-[2.1rem]"
              } ${tone}`}
            >
              {cue.text}
            </div>
            {cue.sub && (
              <div className="mt-6 max-w-2xl text-[15px] leading-relaxed text-con-ink2">
                {cue.sub}
              </div>
            )}
          </div>

          <div className="flex items-center justify-center gap-3 border-t border-con-line px-6 py-4">
            <Btn dark kind="ghost" onClick={back}>&larr; back</Btn>
            <Btn dark kind="solid" onClick={next}>next &rarr;</Btn>
          </div>
        </div>
      )}
    </main>
  );
}
