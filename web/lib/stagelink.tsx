"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

/**
 * The stage's end of the autopilot link.
 *
 * Mounted once in the root layout, so any page of the app can be driven from
 * the Director window during a recording. The two windows talk over a
 * BroadcastChannel rather than a window handle: no popup to be blocked,
 * navigation goes through the Next router so the recorded window never flashes
 * white, and the link survives the stage being closed and reopened.
 *
 * The important word is *addressed*. A BroadcastChannel reaches every tab of
 * the origin, and every tab mounts this listener — so a broadcast "click book"
 * was performed once per open tab. With the app open in two tabs, one click
 * booked every appointment twice and put two of each on the family's phone,
 * which is exactly the duplication that showed up on the real calendar.
 *
 * So every command is ADDRESSED. Each tab holds an id, answers a roll-call
 * with it, and acts only on messages carrying that id. The Director picks one
 * respondent and speaks to it alone; the others stay spectators no matter how
 * many are open.
 *
 * The id is not tied to how the window was opened. Requiring a ?stage= nonce
 * in the URL worked only when the Director's popup survived — open the stage
 * any other way, which is exactly what happens when a browser blocks popups,
 * and the window sat there ignoring everything. A tab that cannot be claimed
 * is as broken as a tab that acts twice.
 */

export const STAGE_CHANNEL = "vitahome-stage";
export const STAGE_PARAM = "stage";
const STAGE_KEY = "vitahome:stageId";

export type StageMessage =
  | { from?: string; to?: string; type: "nav"; path: string }
  | { from?: string; to?: string; type: "external"; url: string }
  | { from?: string; to?: string; type: "click"; auto: string }
  | { from?: string; to?: string; type: "hello" }
  | { from?: string; to?: string; type: "here"; page?: string };

/** This tab's stage identity, minted on first use. Per-tab, not per-browser. */
export function stageId(): string {
  let id = sessionStorage.getItem(STAGE_KEY);
  if (!id) {
    // A nonce in the URL wins, so a window the Director opened itself has an
    // id the Director already knows and can select without asking.
    id = new URLSearchParams(window.location.search).get(STAGE_PARAM)
         || "s-" + Math.random().toString(36).slice(2, 8);
    sessionStorage.setItem(STAGE_KEY, id);
  }
  return id;
}

export function StageLink() {
  const router = useRouter();
  const pathname = usePathname();

  // The Director is a page of this app, so it mounts this listener too. It
  // must never answer the roll-call: offering itself as a stage lets it drive
  // its own teleprompter off the screen, and pads the count the presenter
  // reads to decide whether a stray window is open.
  const isDirector = pathname?.startsWith("/director") ?? false;

  useEffect(() => {
    // Mint this tab's id on mount. Read straight from the URL rather than
    // useSearchParams: this component sits in the root layout, and
    // useSearchParams opts every page out of static prerendering unless each
    // one is wrapped in Suspense.
    //
    // sessionStorage rather than localStorage: the id belongs to this tab and
    // must not leak into the next window the user opens.
    stageId();
  }, []);

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined" || isDirector) return;
    const ch = new BroadcastChannel(STAGE_CHANNEL);

    ch.onmessage = (e: MessageEvent<StageMessage>) => {
      const m = e.data;
      if (!m || typeof m !== "object") return;

      const me = stageId();

      // Answer the roll-call so the Director can show what is out there and
      // choose. Answering is not acting.
      if (m.type === "hello") {
        ch.postMessage({ type: "here", from: me, to: m.from,
                         page: window.location.pathname } as StageMessage);
        return;
      }

      // Exactly one tab is the stage: the one the Director addressed.
      if (m.to !== me) return;

      if (m.type === "nav") {
        router.push(m.path);
        return;
      }

      // The one hop out of the app, to put the Cloud Run URL in the address
      // bar. That page returns here by itself.
      if (m.type === "external") {
        window.location.href = m.url;
        return;
      }

      if (m.type === "click") {
        const t0 = Date.now();
        const tryClick = () => {
          const el = document.querySelector<HTMLElement>(`[data-auto="${m.auto}"]`);
          if (el) return el.click();
          if (Date.now() - t0 < 15000) setTimeout(tryClick, 200);
        };
        tryClick();
      }
    };

    return () => ch.close();
  }, [router, isDirector]);

  return null;
}
