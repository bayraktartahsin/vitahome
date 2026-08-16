"use client";

import { useEffect, useRef } from "react";

/**
 * Poll while the tab is visible, and stop the moment it is not.
 *
 * Every console screen here reads real Firestore documents on a timer — the
 * fleet grid alone is around four hundred reads per refresh. A tab left open
 * overnight on a laptop nobody is looking at bills for every one of those and
 * shows them to nobody.
 *
 * The Page Visibility API makes that free to avoid: background the tab and the
 * polling stops; come back and it refreshes immediately, so the screen is never
 * stale when someone is actually looking at it.
 */
export function usePoll(fn: () => void | Promise<void>, ms: number) {
  const saved = useRef(fn);
  saved.current = fn;

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;

    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };

    const start = () => {
      if (timer) return;
      void saved.current();          // refresh on resume, not on the next tick
      timer = setInterval(() => void saved.current(), ms);
    };

    const onVisibility = () =>
      document.visibilityState === "visible" ? start() : stop();

    onVisibility();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [ms]);
}
