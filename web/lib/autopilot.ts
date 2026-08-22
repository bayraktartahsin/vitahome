/**
 * The autopilot — it drives the demo so the presenter only has to talk.
 *
 * Runs in the Director window (never recorded) and controls a second window
 * (the stage, which IS recorded) through a same-origin window handle: it
 * navigates the stage and clicks its buttons, so every action looks exactly
 * like a human did it — same spinners, same status lines, same animations.
 *
 * Three constraints shaped what is below.
 *
 *   1. Four minutes, hard. Only the first four are evaluated, so the arc is
 *      budgeted to land at ~3:45 with the closing line intact. Every cue's
 *      hold was set from its word count at 2.6 words/second plus a breath —
 *      see scripts/time-script.mjs, which fails the build if the total drifts.
 *
 *   2. Unedited, live execution. Nothing here is faked or pre-rendered. Slow
 *      agents are FIRED EARLY, in the background, while the narration is still
 *      on the previous beat — that is how a 14-second Pub/Sub round trip fits
 *      inside four minutes without a cut: overlap, not editing.
 *
 *   3. Every spoken claim is checked against the running system. The holds for
 *      the async beats are the measured latencies, not estimates:
 *        book + reconcile → refusal  12s
 *        kill drill (dispatch→SKIP)  14s
 *        observation → escalation    13s
 */

export type Step = {
  /** Read this aloud, word for word. */
  say?: string;
  /** Small grey hint under the line — stage direction, never spoken. */
  note?: string;
  /** Point the stage window here first. */
  page?: string;
  /** Click [data-auto="…"] in the stage window. */
  click?: string;
  /** Fire an API call directly, to start a slow agent ahead of its cue. */
  fire?: string;
  /** Hold this long before advancing, in ms. */
  ms: number;
  /** Say nothing — the screen is the evidence. */
  silent?: boolean;
  /** Pick up the phone and show it to camera. */
  phone?: boolean;
};

export const STAGE_ORIGIN = "https://vitahome.vitamedas.com";
export const GATEWAY = "https://vitahome-gateway-205100594497.us-central1.run.app";

export const SCRIPT: Step[] = [
  // ── 0:00 · the paper ────────────────────────────────────────────────────
  {
    page: "/capture",
    say: "A real discharge summary. Twelve instructions. One of them kills him if it is missed. Find it — ten seconds.",
    note: "the document is on screen · say this over it",
    ms: 8600,
  },
  {
    silent: true,
    say: "— the document stays on screen · let them read —",
    note: "say NOTHING. the audience is failing to find it. that is the point.",
    ms: 6000,
  },
  {
    say: "It took me three readings. I was in another country when my family got this one.",
    note: "flat voice · say it once · never mention it again",
    ms: 7100,
  },

  // ── 0:21 · the parse ────────────────────────────────────────────────────
  { say: "So we hand the page to the fleet. No typing, no forms.",
    note: "the parse starts by itself", click: "sample", ms: 5500 },
  {
    silent: true,
    say: "— it is reading the page —",
    note: "say nothing until the list stops appearing",
    ms: 4500,
  },
  { say: "Three seconds.",
    note: "READ THE REAL NUMBER. the screen shows two: say the end-to-end one, which is the one the counter was climbing to.",
    ms: 1700 },
  {
    say: "Top of the list, in red: do not stop ticagrelor. Stopping a blood thinner early after a stent is how people die feeling fine.",
    ms: 10100,
  },
  {
    say: "On the page it was line seven, same font as no lifting over ten pounds. Here it is first, because it is fatal. The line underneath, the fleet wrote itself.",
    ms: 12400,
  },

  // ── 0:56 · execution ────────────────────────────────────────────────────
  {
    page: "/console",
    say: "Now the part nobody builds — someone has to carry them out. Usually a daughter with a phone tree.",
    ms: 8200,
  },
  { click: "book", say: "Watch the counters. And watch my phone.", ms: 3600 },
  {
    click: "recon",
    fire: "coach",
    silent: true,
    say: "— appointments land at 9s · the refusal at 12s —",
    note: "silence · wait for the purple REFUSED card",
    ms: 12500,
  },
  {
    fire: "pharmacist",
    say: "Then it stopped. It refused. It did not guess — it assembled both readings, each citing its source line, and put a human in front of the decision.",
    ms: 11700,
  },
  {
    phone: true,
    say: "Those appointments are in my phone's calendar — written through the Calendar API, same idempotency keys as the record. Remember this phone.",
    note: "refresh the calendar on the phone — the mirrored window is already in shot",
    ms: 9400,
  },
  {
    // Deliberately not a number. Two agents refuse over the same drug — the
    // Reconciler declining to rule, then the Pharmacist declining to schedule
    // around an unruled drug — and which of them has landed depends on the
    // second. A count said aloud that the screen contradicts is a bad trade for
    // a word.
    say: "Look at that counter: refused. Everyone here is optimising for how much their agents do alone. In medicine that is the wrong axis.",
    note: "point at the refused tile — it may read 1 or 2, both are correct",
    ms: 9700,
  },

  // ── 1:47 · the refusal travels ──────────────────────────────────────────
  {
    page: "/today",
    say: "The Pharmacist built the day. Amlodipine is held, not dropped — don't take this one until you hear back. The refusal travelled. The Coach asked one question.",
    note: "the question on screen is chosen live — you may read it out if it lands",
    ms: 11300,
  },

  // ── 2:00 · the kill ─────────────────────────────────────────────────────
  {
    page: "/console/drill",
    say: "That was the happy path. Let me break it. This kills a real worker process, no cleanup. The Scheduler runs on its own Cloud Run service.",
    ms: 10900,
  },
  { click: "arm-scheduler", silent: true, say: "— arming —", note: "no words", ms: 1200 },
  { click: "start", silent: true, say: "— dispatching —", note: "no words", ms: 1500 },
  {
    page: "/console",
    fire: "chest_pain",
    silent: true,
    say: "— DOWN at 3s · REDO at 11s · SKIP at 14s —",
    note: "SILENCE. this is the money shot — do not fill it.",
    ms: 16000,
  },
  {
    say: "The process is gone. Nothing caught it. The message was never acknowledged, so Pub/Sub redelivered it, Cloud Run gave a fresh container — new worker id — and the finished step says SKIP. One appointment. One calendar event. Not two.",
    ms: 16300,
  },

  // ── 2:47 · Google Cloud proof (the rules require it) ────────────────────
  {
    page: "__gateway__/health/deep",
    fire: "lightheaded",
    say: "And this is what it runs on. Cloud Run, the Healthcare API, Gemini — every row checked by calling it, just now.",
    note: "the address bar shows the .run.app URL — that is the proof",
    ms: 9400,
  },

  // ── 2:56 · escalation, then restraint ───────────────────────────────────
  {
    page: "/console",
    say: "Monitoring has been armed since minute one, against the red flags on this page. Chest pain — it paged a clinician, five-minute clock. It did not treat or advise. No agent can close it.",
    ms: 14000,
  },
  {
    say: "Now the harder one. Same monitor, different reading — lightheaded on standing.",
    ms: 5500,
  },
  {
    silent: true,
    say: "— nothing will appear in the queue —",
    note: "let it settle · the audit stream shows the decision",
    ms: 4000,
  },
  {
    say: "Nothing. It decided a human was not needed — and wrote down why, the strongest argument against itself, and what would have changed its mind. Anything can panic. Restraint is expensive.",
    ms: 12800,
  },

  // ── 3:35 · scale ────────────────────────────────────────────────────────
  {
    page: "/console/fleets",
    fire: "storm",
    say: "Two hundred fleets. Every square is a real patient record. Synthetic patients. Real infrastructure.",
    ms: 6300,
  },

  // ── 3:43 · close ────────────────────────────────────────────────────────
  {
    say: "The hospital saves your life. Then it hands you a piece of paper.",
    note: "the closing line · no action needed",
    ms: 5900,
  },
  { say: "We take it from there.", ms: 2800 },
  {
    silent: true,
    say: "— three seconds, then STOP the recording —",
    note: "do not say thank you",
    ms: 3000,
  },
];

/** Slow agents the autopilot starts early so their results land on cue. */
export const FIRE: Record<string, { path: string; body?: unknown }> = {
  coach: { path: "/demo/dispatch", body: { patientId: "p_hero", agent: "coach" } },
  pharmacist: { path: "/demo/dispatch", body: { patientId: "p_hero", agent: "pharmacist" } },
  chest_pain: { path: "/demo/observe?scenario=chest_pain&patientId=p_hero" },
  lightheaded: { path: "/demo/observe?scenario=lightheaded_on_standing&patientId=p_hero" },
  storm: { path: "/demo/storm?count=60" },
};

export const TOTAL_MS = SCRIPT.reduce((a, s) => a + s.ms, 0);
