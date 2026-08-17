"use client";

import { useState } from "react";
import Link from "next/link";
import { API } from "@/lib/api";
import { AGENTS, AgentMark } from "@/lib/agents";

export { AGENTS, AgentMark };

/**
 * The shared design system. One identity across seven pages.
 *
 * Rules it enforces:
 *  - no emoji anywhere. Agents carry a two-letter monogram set in their color.
 *  - every action gives immediate feedback: per-button spinners and a status
 *    line that says what is happening, how long it took, and what failed.
 *  - one wordmark, one top bar, one button language per surface.
 */

/* -------------------------------------------------------------- wordmark -- */

export function Mark({ size = 18 }: { size?: number }) {
  // A green cross in a square — the pharmacy sign, not the Red Cross emblem.
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden>
      <rect width="18" height="18" rx="4" fill="#2E6B4E" />
      <path d="M7.5 4h3v3.5H14v3h-3.5V14h-3v-3.5H4v-3h3.5z" fill="#F7F3EA" />
    </svg>
  );
}

export function Wordmark({ dark = false }: { dark?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2">
      <Mark />
      <span
        className="font-display text-[17px] font-semibold tracking-tight"
        style={{ color: dark ? "#DDE6DE" : "#232B22" }}
      >
        VitaHome
      </span>
    </Link>
  );
}

/* ---------------------------------------------------------------- topbar -- */

export function TopBar({
  dark = false,
  center,
  links,
}: {
  dark?: boolean;
  center?: React.ReactNode;
  links: { href: string; label: string; tone?: "danger" }[];
}) {
  return (
    <header
      className={
        dark
          ? "border-b border-con-line bg-con-bg/95 px-5 py-3"
          : "border-b border-fam-line bg-fam-bg/95 px-5 py-3"
      }
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <Wordmark dark={dark} />
        {center && (
          <div
            className={`hidden font-mono text-[11px] tracking-wide sm:block ${
              dark ? "text-con-ink2" : "text-fam-ink2"
            }`}
          >
            {center}
          </div>
        )}
        <nav className="flex items-center gap-4">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`text-[12px] font-medium tracking-wide transition ${
                l.tone === "danger"
                  ? dark
                    ? "text-con-danger hover:underline"
                    : "text-fam-danger hover:underline"
                  : dark
                    ? "text-con-ink2 hover:text-con-ink"
                    : "text-fam-ink2 hover:text-fam-ink"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

/* --------------------------------------------------------------- buttons -- */

export function Btn({
  children,
  onClick,
  kind = "solid",
  dark = false,
  busy = false,
  disabled = false,
  title,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  kind?: "solid" | "outline" | "danger" | "ghost";
  dark?: boolean;
  busy?: boolean;
  disabled?: boolean;
  title?: string;
}) {
  const base =
    "inline-flex items-center gap-2 whitespace-nowrap px-3.5 py-2 text-[13px] font-medium transition active:translate-y-px disabled:cursor-default disabled:opacity-45";
  const styles = dark
    ? {
        solid:
          "rounded-con bg-con-accent text-[#0B0F0D] hover:brightness-110 font-semibold",
        outline:
          "rounded-con border border-con-line font-mono text-[12px] text-con-ink2 hover:border-con-accent/60 hover:text-con-ink",
        danger:
          "rounded-con border border-con-danger/50 font-mono text-[12px] text-con-danger hover:bg-con-danger/10",
        ghost: "rounded-con text-con-ink2 hover:text-con-ink",
      }
    : {
        solid: "rounded-fam bg-fam-accent text-fam-bg shadow-sheet hover:brightness-110 font-semibold",
        outline:
          "rounded-fam border border-fam-line bg-fam-surface text-fam-ink hover:bg-fam-surface2",
        danger:
          "rounded-fam border border-fam-danger/40 text-fam-danger hover:bg-fam-danger/5",
        ghost: "rounded-fam text-fam-ink2 hover:text-fam-ink",
      };
  return (
    <button
      onClick={onClick}
      disabled={disabled || busy}
      title={title}
      className={`${base} ${styles[kind]}`}
    >
      {busy && <span className="vh-spin" aria-hidden />}
      {children}
    </button>
  );
}

/* ----------------------------------------------------- action feedback --- */

export type Note = { text: string; tone: "run" | "ok" | "err" } | null;

/**
 * Runs actions with visible feedback. A click is never silent again: the
 * pressed button shows a spinner, and the status line reports what happened
 * and how long it took — or exactly what failed.
 */
export function useRunner() {
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Note>(null);

  async function run(key: string, label: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setNote({ text: `${label}…`, tone: "run" });
    const t0 = performance.now();
    try {
      await fn();
      setNote({
        text: `${label} — done in ${((performance.now() - t0) / 1000).toFixed(1)}s`,
        tone: "ok",
      });
    } catch (e) {
      setNote({
        text: `${label} — failed: ${e instanceof Error ? e.message : String(e)}`,
        tone: "err",
      });
    } finally {
      setBusy(null);
    }
  }

  return { busy, note, run };
}

export function StatusLine({ note, dark = false }: { note: Note; dark?: boolean }) {
  if (!note) return null;
  const tone =
    note.tone === "err"
      ? dark
        ? "text-con-danger"
        : "text-fam-danger"
      : note.tone === "ok"
        ? dark
          ? "text-con-accent"
          : "text-fam-accent"
        : dark
          ? "text-con-ink2"
          : "text-fam-ink2";
  return (
    <p className={`font-mono text-[11px] ${tone}`} role="status">
      {note.tone === "run" && <span className="vh-spin mr-1.5" aria-hidden />}
      {note.text}
    </p>
  );
}

/* ------------------------------------------------------------------ api --- */

/** fetch that throws a readable error instead of failing silently. */
export async function api(path: string, init?: RequestInit): Promise<Response> {
  const r = await fetch(`${API}${path}`, init);
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json())?.detail ?? "";
    } catch {
      /* no body */
    }
    throw new Error(detail || `HTTP ${r.status}`);
  }
  return r;
}

export const post = (path: string, body?: unknown) =>
  api(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

/* ------------------------------------------------------------ audit tags -- */

/** Word tags for the audit stream — no emoji. */
export const AUDIT_TAG: Record<string, { tag: string; cls: string }> = {
  AGENT_DOWN: { tag: "down", cls: "text-con-danger" },
  redelivery: { tag: "redo", cls: "text-con-warn" },
  skip: { tag: "skip", cls: "text-con-info" },
  refusal: { tag: "refuse", cls: "text-con-hold" },
  escalation: { tag: "page", cls: "text-con-danger" },
  lease: { tag: "lease", cls: "text-con-ink2" },
  action: { tag: "act", cls: "text-con-ink2" },
  heartbeat: { tag: "beat", cls: "text-con-ink2" },
  access: { tag: "read", cls: "text-con-ink2" },
};
