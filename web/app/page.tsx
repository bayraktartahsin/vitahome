import Link from "next/link";
import { AGENTS, AgentMark } from "@/lib/agents";
import { TopBar } from "@/lib/ui";

/**
 * The family surface's front door. A document, set properly — not a dashboard.
 * The fleet is presented as a roster with hairline rules, the way a masthead
 * lists its editors; the three proof links are the paths a judge actually takes.
 */
export default function Home() {
  return (
    <main className="theme-family min-h-screen font-sans">
      <TopBar
        links={[
          { href: "/today", label: "Today" },
          { href: "/console", label: "Console" },
          { href: "/architecture", label: "Architecture" },
        ]}
      />

      <div className="mx-auto max-w-3xl px-6 pb-20 pt-16 md:pt-24">
        <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-fam-ink2">
          Vitamedas Inc. — the Vita family
        </p>

        <h1 className="mt-4 font-display text-[2.6rem] font-semibold leading-[1.08] text-fam-ink md:text-[3.4rem]">
          The hospital saves your life, then hands you a piece of paper.
        </h1>

        <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-fam-ink2">
          <span className="font-medium text-fam-ink">We take it from there.</span>{" "}
          Photograph the discharge papers. Seven agents reconcile the medications,
          book every follow-up, turn the doses into a real clock, and watch for the
          warning signs written on that page — and hand every clinical judgement to
          a licensed human.
        </p>

        <div className="mt-9 flex flex-wrap items-center gap-3">
          <Link
            href="/capture"
            className="rounded-fam bg-fam-accent px-5 py-3 text-sm font-semibold text-fam-bg shadow-sheet transition hover:brightness-110 active:translate-y-px"
          >
            Photograph a document
          </Link>
          <Link
            href="/console"
            className="rounded-fam border border-fam-line bg-fam-surface px-5 py-3 text-sm font-medium text-fam-ink transition hover:bg-fam-surface2"
          >
            Watch the fleet work
          </Link>
        </div>

        {/* ------------------------------------------------------ roster --- */}
        <section className="mt-16">
          <div className="flex items-baseline justify-between border-b-2 border-fam-ink pb-2">
            <h2 className="font-display text-lg font-semibold text-fam-ink">The fleet</h2>
            <span className="font-mono text-[11px] text-fam-ink2">
              seven agents · all live
            </span>
          </div>
          <ul>
            {Object.entries(AGENTS).map(([id, a]) => (
              <li
                key={id}
                className="flex items-baseline gap-4 border-b border-fam-line py-3.5"
              >
                <AgentMark agent={id} />
                <span className="w-24 shrink-0 font-medium text-fam-ink">{a.name}</span>
                <span className="hidden w-24 shrink-0 font-mono text-[11px] text-fam-ink2 sm:block">
                  {a.verb}
                </span>
                <span className="text-[13.5px] leading-snug text-fam-ink2">{a.duty}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] leading-relaxed text-fam-ink2">
            Four of the seven can refuse. When the paperwork contradicts itself, the
            fleet does not pick the likelier reading — it assembles both and puts a
            clinician in front of the decision.
          </p>
        </section>

        {/* ------------------------------------------------------- proof --- */}
        <section className="mt-14 grid gap-3 sm:grid-cols-3">
          {[
            ["Kill an agent", "A real process dies mid-task. Watch it recover without double-booking.", "/console/drill"],
            ["200 fleets", "Every square is a real patient record. Hand them all real work.", "/console/fleets"],
            ["The architecture", "How work flows, and how a task survives its worker dying.", "/architecture"],
          ].map(([t, d, href]) => (
            <Link
              key={href}
              href={href}
              className="group rounded-fam border border-fam-line bg-fam-surface p-4 shadow-sheet transition hover:border-fam-accent/50"
            >
              <div className="flex items-center justify-between">
                <span className="font-display text-[15px] font-semibold text-fam-ink">{t}</span>
                <span className="font-mono text-xs text-fam-ink2 transition group-hover:translate-x-0.5 group-hover:text-fam-accent">
                  &rarr;
                </span>
              </div>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-fam-ink2">{d}</p>
            </Link>
          ))}
        </section>

        <footer className="mt-16 border-t border-fam-line pt-6 text-[12px] leading-relaxed text-fam-ink2">
          VitaHome never diagnoses and never prescribes. It executes instructions a
          licensed clinician already wrote, and hands every ambiguity to a person.
          All demo patients are synthetic. Built on Google Cloud by{" "}
          <span className="text-fam-ink">Vitamedas Inc.</span>, makers of Vita.
        </footer>
      </div>
    </main>
  );
}
