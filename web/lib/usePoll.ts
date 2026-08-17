"use client";

import { useEffect, useRef } from "react";

/**
 * Poll while the tab is visible; stop the moment it is not.
 *
 * Every console screen reads real Firestore documents on a timer, so a tab
 * left open overnight would bill for reads nobody sees. Background the tab and
 * polling stops; return and it refreshes immediately.
 *
 * Two details that exist because their absence looked like a broken app:
 *  - one fetch always runs on mount, even if the document reports itself
 *    hidden (embedded previews and some webviews do), so the screen never
 *    sits on placeholder dashes with a working backend behind it.
 *  - window focus also triggers a refresh, so alt-tabbing back never shows
 *    stale numbers.
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
      void saved.current();
      timer = setInterval(() => void saved.current(), ms);
    };

    const onVisibility = () =>
      document.visibilityState === "visible" ? start() : stop();
    const onFocus = () => void saved.current();

    void saved.current(); // always at least once — see note above
    if (document.visibilityState === "visible") start();

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onFocus);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onFocus);
    };
  }, [ms]);
}
