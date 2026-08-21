"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Btn, StatusLine, TopBar, post, useRunner } from "@/lib/ui";
import { FIRE, GATEWAY, SCRIPT, STAGE_ORIGIN, TOTAL_MS, type Step } from "@/lib/autopilot";
import { STAGE_CHANNEL, STAGE_PARAM, type StageMessage } from "@/lib/stagelink";
import { startTicker } from "@/lib/ticker";

/**
 * The Director — autopilot + teleprompter.
 *
 * This window is NEVER recorded. A second window — the stage — is, and this
 * one drives it: navigation and clicks are broadcast to the stage, which
 * performs them itself, so the recorded window shows a normal human session
 * with real spinners, real status lines and real animations.
 *
 * The presenter's whole job becomes reading the large line on this screen.
 */

const mmss = (ms: number) =>
  `${Math.floor(ms / 60000)}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, "0")}`;

export default function Director() {
  const [i, setI] = useState(-1);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [log, setLog] = useState<string[]>([]);
  const { busy, note, run } = useRunner();

  const abort = useRef(false);
  const paused = useRef(false);

  const say = (s: string) =>
    setLog((l) => [`${new Date().toLocaleTimeString().slice(0, 8)}  ${s}`, ...l].slice(0, 8));

  /* ------------------------------------------------------ stage control -- */

  /* Commands are ADDRESSED, not broadcast. A BroadcastChannel reaches every tab
     of the origin and every tab mounts the listener, so a broadcast click was
     performed once per open tab — with the app open twice, every appointment
     was booked twice and landed on the phone twice. The Director opens the
     stage carrying a nonce and speaks only to that nonce. */
  const chan = useRef<BroadcastChannel | null>(null);
  const directorId = useRef(Math.random().toString(36).slice(2));
  const [stageNonce, setStageNonce] = useState<string>("");   // what we opened
  const [chosen, setChosen] = useState<string>("");           // who we drive
  const [listening, setListening] = useState<{ id: string; page: string }[]>([]);

  useEffect(() => {
    const c = new BroadcastChannel(STAGE_CHANNEL);
    c.onmessage = (e: MessageEvent<StageMessage>) => {
      const m = e.data;
      if (m?.type === "here" && m.to === directorId.current && m.from) {
        const entry = { id: m.from, page: (m as { page?: string }).page || "?" };
        setListening((l) => (l.some((x) => x.id === entry.id) ? l : [...l, entry]));
      }
    };
    chan.current = c;
    return () => c.close();
  }, []);

  /* Read the target through a ref rather than closing over state: `start` runs
     a four-minute loop, and a value captured when it began would be the value
     from before the stage was chosen. */
  const target = useRef("");
  useEffect(() => { target.current = chosen; }, [chosen]);

  const send = useCallback((m: StageMessage) => {
    chan.current?.postMessage({ ...m, from: directorId.current, to: target.current });
  }, []);

  /** Roll-call: who is out there, and which one do we drive? */
  const roll = useCallback(() => {
    setListening([]);
    chan.current?.postMessage({ type: "hello", from: directorId.current } as StageMessage);
  }, []);

  // Choose automatically where the choice is obvious: the window we opened
  // ourselves, or the only one that answered. Ask only when it is genuinely
  // ambiguous, rather than silently driving the wrong window.
  useEffect(() => {
    if (listening.some((x) => x.id === stageNonce)) { setChosen(stageNonce); return; }
    if (listening.length === 1) { setChosen(listening[0].id); return; }
    if (listening.length === 0) setChosen("");
  }, [listening, stageNonce]);

  useEffect(() => {
    const t = setTimeout(roll, 600);
    return () => clearTimeout(t);
  }, [roll]);

  const stageUrl = stageNonce
    ? `${STAGE_ORIGIN}/capture?${STAGE_PARAM}=${stageNonce}`
    : "";

  const openStage = useCallback(() => {
    const nonce = Math.random().toString(36).slice(2, 10);
    setStageNonce(nonce);
    const url = `${STAGE_ORIGIN}/capture?${STAGE_PARAM}=${nonce}`;
    const w = window.open(url, "vitahome_stage_" + nonce, "width=1440,height=900");
    say(w
      ? "stage opened — record THAT window"
      : "popup blocked — open the address shown below in a second window yourself");
    setTimeout(() => {
      setListening([]);
      chan.current?.postMessage({ type: "hello", from: directorId.current } as StageMessage);
    }, 1500);
  }, []);

  const navigate = useCallback((page: string) => {
    if (page.startsWith("__gateway__")) {
      // The one hop out of the app: the *.run.app address bar is the contest's
      // proof that the backend runs on Google Cloud. That page returns here on
      // its own, so this needs no handle on the stage window.
      const back = encodeURIComponent(`${STAGE_ORIGIN}/console`);
      send({ type: "external",
             url: `${GATEWAY}${page.replace("__gateway__", "")}?back=${back}&after=8000` });
    } else {
      send({ type: "nav", path: page });
    }
    say(`stage → ${page}`);
  }, [send]);

  const clickStage = useCallback(async (auto: string) => {
    send({ type: "click", auto });
    say(`stage click → ${auto}`);
    return true;
  }, [send]);

  /** Start a slow agent early, in the background, so it lands on cue. */
  const fire = useCallback(async (key: string) => {
    const f = FIRE[key];
    if (!f) return;
    post(f.path, f.body).catch(() => {});
    say(`fired → ${key}`);
  }, []);

  /* ------------------------------------------------------------- runner -- */

  /** Wall clock that stops while paused, so the 4:00 budget stays honest. */
  const clock = useRef(0);
  const skip = useRef(false);
  /* Overshoot carried into the next cue. A browser throttles timers in a window
     it considers hidden, so a cue can end up to a second late; unchecked, that
     drift across twenty-nine cues is enough to push a 3:52 run past four
     minutes. Each cue gives back what the last one took, never dropping below
     two-thirds of its own hold — losing a little air is fine, losing the end of
     a sentence is not. */
  const debt = useRef(0);

  /* Ticks come from a worker, not from this page's own timers: a browser slows
     a hidden page's setTimeout to once a minute, and the Director is precisely
     the window that ends up behind the one being recorded. Every waiting cue
     subscribes here; the worker fans out to them. */
  const waiters = useRef(new Set<() => void>());
  useEffect(() => {
    const t = startTicker();
    t.onTick(() => waiters.current.forEach((fn) => fn()));
    return () => t.stop();
  }, []);

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      const budget = Math.max(ms * 0.66, ms - debt.current);
      const began = Date.now();
      let left = budget;
      let last = began;

      const finish = (carry: boolean) => {
        waiters.current.delete(tick);
        debt.current = carry ? Math.max(0, Date.now() - began - budget) : 0;
        resolve();
      };

      const tick = () => {
        const now = Date.now();
        const dt = now - last;
        last = now;
        if (abort.current || skip.current) {
          skip.current = false;
          return finish(false);
        }
        if (!paused.current) {
          left -= dt;
          clock.current += dt;
          setElapsed(clock.current);
        }
        if (left <= 0) finish(true);
      };

      waiters.current.add(tick);
    });

  const start = useCallback(async () => {
    abort.current = false;
    paused.current = false;
    skip.current = false;
    clock.current = 0;
    debt.current = 0;
    setRunning(true);
    setElapsed(0);

    for (let n = 0; n < SCRIPT.length; n++) {
      if (abort.current) break;
      const s: Step = SCRIPT[n];
      setI(n);
      if (s.page) navigate(s.page);
      if (s.fire) await fire(s.fire);
      if (s.click) await clickStage(s.click);
      await sleep(s.ms);
    }

    setRunning(false);
    say("script complete — stop the recording");
  }, [navigate, fire, clickStage]);

  /* ---------------------------------------------------------- shortcuts -- */

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        e.preventDefault();
        paused.current = !paused.current;
        say(paused.current ? "PAUSED" : "resumed");
        setI((v) => v); // nudge a repaint
      }
      if (e.key === "ArrowRight") { e.preventDefault(); skip.current = true; }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // A hidden Director is the one setup mistake that silently ruins a take.
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const on = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);

  const cue = i >= 0 ? SCRIPT[i] : null;
  const over = elapsed > 240000;
  // where the script says we should be by now
  const planned = SCRIPT.slice(0, Math.max(i, 0)).reduce((a, s) => a + s.ms, 0);
  const drift = elapsed - planned;

  /* -------------------------------------------------------------- view -- */

  if (!running && i < 0) {
    return (
      <main className="theme-console min-h-screen font-sans">
        <TopBar dark center="director · autopilot — this window is NOT recorded"
          links={[{ href: "/console", label: "Console" }]} />
        <div className="mx-auto max-w-3xl px-6 py-10">
          <h1 className="font-display text-2xl font-semibold text-con-ink">
            Autopilot — you only have to talk
          </h1>
          <p className="mt-3 text-[14px] leading-relaxed text-con-ink2">
            This window drives a second window for you: every navigation and every
            click happens automatically, on cue. You read the big line, and stop
            talking when it says to. Total run: <b className="text-con-ink">{mmss(TOTAL_MS)}</b>{" "}
            (the contest evaluates only the first 4:00).
          </p>

          <ol className="mt-6 list-decimal space-y-3 pl-5 text-[14px] leading-relaxed text-con-ink2">
            <li>Press <b className="text-con-ink">1 · reset</b> then <b className="text-con-ink">2 · seed</b> below, and wait for each to say done.</li>
            <li>Press <b className="text-con-ink">3 · seed 200 fleets</b> and wait about twenty seconds.</li>
            <li>Press <b className="text-con-ink">4 · open the stage window</b>. A second window appears — <b className="text-con-ink">that is the one you record.</b> Move it to your main screen and make it big. (If your browser blocks the popup, just open{" "}<b className="text-con-ink">vitahome.vitamedas.com/capture</b> in a second window yourself — it works the same way.)</li>
            <li>Put THIS window where the camera cannot see it (second screen, or off to one side).</li>
            <li>Start your screen recording of the stage window.</li>
            <li>Press <b className="text-con-ink">5 · GO</b> and read the big line. Space bar pauses if you need a moment; the right arrow skips ahead.</li>
          </ol>

          <div className="mt-7 flex flex-wrap items-center gap-2">
            <Btn dark kind="outline" busy={busy === "reset"}
              onClick={() => run("reset", "resetting the demo patient", () => post("/demo/reset?patientId=p_hero"))}>
              1 · reset
            </Btn>
            <Btn dark kind="outline" busy={busy === "seed"}
              onClick={() => run("seed", "seeding Robert Hayes", () => post("/demo/seed"))}>
              2 · seed
            </Btn>
            <Btn dark kind="outline" busy={busy === "cohort"}
              onClick={() => run("cohort", "seeding 200 fleets for the scale shot", () => post("/demo/cohort?count=200"))}>
              3 · seed 200 fleets
            </Btn>
            <Btn dark kind="outline" onClick={openStage}>
              4 · open the stage window
            </Btn>
            <Btn dark kind="solid" disabled={!chosen} onClick={start}>
              5 · GO &rarr;
            </Btn>
          </div>
          <div className="mt-2 min-h-[18px]"><StatusLine dark note={note} /></div>

          <div className="mt-5 rounded-con border border-con-line bg-con-panel p-4">
            <div className="flex items-center justify-between gap-4">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-con-ink2">
                stage link
              </span>
              <Btn dark kind="ghost" onClick={roll}>re-check</Btn>
            </div>

            <p className={`mt-2 font-mono text-[12px] ${
              chosen ? "text-con-accent" : "text-con-warn"}`}>
              {listening.length === 0
                ? "no window answering — open the stage, then press re-check"
                : chosen
                  ? `driving ${listening.find((x) => x.id === chosen)?.page ?? "the stage"}`
                    + (listening.length > 1 ? ` · ${listening.length} windows found` : " · one window")
                  : `${listening.length} windows answered — pick the one you are recording`}
            </p>

            {listening.length > 1 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {listening.map((x) => (
                  <button
                    key={x.id}
                    onClick={() => setChosen(x.id)}
                    className={`rounded-con border px-3 py-1.5 font-mono text-[11px] transition ${
                      chosen === x.id
                        ? "border-con-accent text-con-accent"
                        : "border-con-line text-con-ink2 hover:text-con-ink"
                    }`}
                  >
                    {x.page} · {x.id.slice(0, 6)}
                  </button>
                ))}
              </div>
            )}

            <p className="mt-3 text-[12px] leading-relaxed text-con-ink2">
              Only the selected window takes commands. Every other tab of the app
              is a spectator — before this existed, a second open tab carried out
              every click a second time and booked every appointment twice.
            </p>
            {stageUrl && (
              <p className="mt-2 break-all font-mono text-[11px] text-con-ink2">
                popup blocked? open this yourself, then press re-check: {stageUrl}
              </p>
            )}
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="theme-console flex min-h-screen flex-col font-sans">
      {/* status strip */}
      <div className="flex items-center justify-between border-b border-con-line px-6 py-2 font-mono text-[12px]">
        <span className="text-con-ink2">cue {i + 1} / {SCRIPT.length}</span>
        <span className={over ? "text-con-danger" : "text-con-accent"}>
          {mmss(elapsed)} / {mmss(TOTAL_MS)}
          {over
            ? " · OVER 4:00"
            : Math.abs(drift) > 3000
              ? ` · ${drift > 0 ? "+" : "−"}${Math.round(Math.abs(drift) / 1000)}s`
              : " · on time"}
        </span>
        <span className="text-con-ink2">space = pause · right arrow = next cue</span>
      </div>

      {hidden && (
        <div className="bg-con-danger px-6 py-2 text-center font-mono text-[12px] text-[#0B0F0D]">
          this window is hidden — keep it visible, or you cannot read the cues
        </div>
      )}

      {/* the cue */}
      <div className="flex flex-1 flex-col items-center justify-center px-10 py-8 text-center">
        <div className={`mb-6 font-mono text-[13px] uppercase tracking-[0.32em] ${
          cue?.silent ? "text-con-accent" : cue?.phone ? "text-con-warn" : "text-con-ink2"
        }`}>
          {cue?.silent ? "silence" : cue?.phone ? "phone — then say" : "say"}
        </div>
        <div className={`max-w-5xl ${
          cue?.silent
            ? "font-mono text-[1.8rem] text-con-accent"
            : "font-display text-[2.2rem] font-semibold leading-snug text-con-ink md:text-[2.7rem]"
        }`}>
          {cue?.say}
        </div>
        {cue?.note && (
          <div className="mt-7 max-w-2xl text-[15px] leading-relaxed text-con-ink2">
            {cue.note}
          </div>
        )}
      </div>

      {/* what the autopilot is doing */}
      <div className="border-t border-con-line px-6 py-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-6">
          <div className="font-mono text-[11px] text-con-ink2">
            {log[0] ?? "—"}
          </div>
          <div className="flex gap-2">
            <Btn dark kind="ghost" onClick={() => { paused.current = !paused.current; setI(v => v); }}>
              pause / resume
            </Btn>
            <Btn dark kind="danger" onClick={() => { abort.current = true; setRunning(false); }}>
              stop
            </Btn>
          </div>
        </div>
      </div>
    </main>
  );
}
