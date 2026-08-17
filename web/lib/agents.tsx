/**
 * The fleet roster — plain data, importable from server and client components
 * alike. (A `"use client"` module exports client references, not values, to
 * server components; the landing page renders this list on the server, so the
 * data has to live on the shared side of that boundary.)
 */
export const AGENTS: Record<
  string,
  { mono: string; name: string; color: string; verb: string; duty: string }
> = {
  parser:     { mono: "Pa", name: "Parser",     color: "#6B9BD1", verb: "reads",         duty: "Document to plan, ranked by what happens if it is missed" },
  reconciler: { mono: "Rc", name: "Reconciler", color: "#C46A8A", verb: "checks",        duty: "New medications against the record; refuses contradictions" },
  scheduler:  { mono: "Sc", name: "Scheduler",  color: "#57A47B", verb: "books",         duty: "Every follow-up, into a real FHIR store" },
  pharmacist: { mono: "Ph", name: "Pharmacist", color: "#C99A4B", verb: "schedules",     duty: "Doses onto a real clock; never invents a time" },
  watchman:   { mono: "Wa", name: "Watchman",   color: "#D07B4A", verb: "watches",       duty: "The red flags written on this document" },
  coach:      { mono: "Co", name: "Coach",      color: "#5FA9A0", verb: "asks",          duty: "One question a day, chosen from what is unknown" },
  escalator:  { mono: "Es", name: "Escalator",  color: "#C9604F", verb: "calls a human", duty: "The only path to a clinical decision — and may decline" },
};

/** Server-safe monogram chip — pure markup, no hooks. */
export function AgentMark({ agent, size = 22 }: { agent: string; size?: number }) {
  const a = AGENTS[agent] ?? { mono: agent.slice(0, 2), color: "#68715F", name: agent };
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 select-none items-center justify-center rounded-[4px] font-mono font-semibold leading-none"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.42,
        background: `${a.color}26`,
        color: a.color,
        boxShadow: `inset 0 0 0 1px ${a.color}55`,
      }}
    >
      {a.mono}
    </span>
  );
}
