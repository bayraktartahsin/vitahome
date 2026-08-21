/**
 * A clock that keeps running when the window is not being looked at.
 *
 * Browsers throttle setTimeout in a page they consider hidden — down to once
 * per minute once the page has been hidden for a while. The Director is
 * exactly the window that gets hidden: the presenter is watching the stage,
 * and on a single-screen setup the Director can end up fully occluded. Driving
 * cue changes from a page timer there meant a run drifting a minute behind
 * inside the first two minutes, which is not a rough edge — it is the whole
 * take lost.
 *
 * A dedicated worker has its own event loop and keeps its timers at full rate.
 * This is a four-line worker whose only job is to say "tick", built from a Blob
 * so it needs no separate file and no bundler configuration.
 *
 * Callers must still measure real elapsed time from Date.now() rather than
 * counting ticks — a tick is a prompt to check the clock, never the clock.
 */

const WORKER_SRC = `
let id = null;
onmessage = (e) => {
  if (e.data === "start" && id === null) id = setInterval(() => postMessage(1), 100);
  if (e.data === "stop" && id !== null) { clearInterval(id); id = null; }
};
`;

export type Ticker = { onTick: (fn: () => void) => void; stop: () => void };

/** Start a 100ms ticker. Falls back to setInterval where workers are absent. */
export function startTicker(): Ticker {
  const listeners = new Set<() => void>();
  const fire = () => listeners.forEach((fn) => fn());

  let stop = () => {};

  try {
    const url = URL.createObjectURL(new Blob([WORKER_SRC], { type: "text/javascript" }));
    const w = new Worker(url);
    w.onmessage = fire;
    w.postMessage("start");
    stop = () => {
      w.postMessage("stop");
      w.terminate();
      URL.revokeObjectURL(url);
    };
  } catch {
    // No worker available — a throttled clock still beats no clock, and the
    // elapsed-time maths downstream is tick-rate independent.
    const h = setInterval(fire, 100);
    stop = () => clearInterval(h);
  }

  return {
    onTick: (fn) => listeners.add(fn),
    stop: () => {
      listeners.clear();
      stop();
    },
  };
}
