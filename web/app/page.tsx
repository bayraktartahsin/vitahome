import Link from "next/link";

/** Family surface — warm light. A kitchen-table product for frightened people. */
export default function Home() {
  return (
    <main className="theme-family min-h-screen">
      <div className="mx-auto max-w-3xl px-6 py-16 md:py-24">
        <div className="inline-flex items-center gap-2 rounded-full border border-fam-line bg-fam-surface px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-fam-ink2">
          <span className="h-1.5 w-1.5 rounded-full bg-fam-accent" />
          VitaHome · by Graviti Labs
        </div>

        <h1 className="mt-6 font-display text-4xl leading-[1.12] text-fam-ink md:text-5xl">
          The hospital saves your life,
          <br />
          then hands you a piece of paper.
        </h1>

        <p className="mt-5 max-w-xl text-lg leading-relaxed text-fam-ink2">
          <span className="text-fam-ink">We take it from there.</span> Photograph the
          papers they gave you. VitaHome reconciles the medications, books every
          follow-up, watches for the warning signs written on that page — and calls a
          human the moment one appears.
        </p>

        <div className="mt-9 flex flex-wrap gap-3">
          <Link
            href="/capture"
            className="rounded-fam bg-fam-accent px-5 py-3 text-sm font-semibold text-white shadow-fam transition hover:opacity-90"
          >
            Photograph a document
          </Link>
          <Link
            href="/console"
            className="rounded-fam border border-fam-line bg-fam-surface px-5 py-3 text-sm font-semibold text-fam-ink transition hover:bg-fam-surface2"
          >
            Clinician console →
          </Link>
          <Link
            href="/architecture"
            className="rounded-fam border border-fam-line bg-fam-surface px-5 py-3 text-sm font-semibold text-fam-ink2 transition hover:bg-fam-surface2 hover:text-fam-ink"
          >
            Architecture
          </Link>
        </div>

        <div className="mt-16 grid gap-4 sm:grid-cols-2">
          {[
            ["📄", "Parser", "reads", "Finds every instruction — and ranks the one that kills if missed."],
            ["💊", "Reconciler", "checks", "New meds against old. Interactions. What to stop."],
            ["📅", "Scheduler", "books", "Every follow-up appointment, without being asked."],
            ["🏥", "Pharmacist", "sends", "Prescriptions routed, doses scheduled."],
            ["👁", "Watchman", "watches", "The red flags on your document, 24/7."],
            ["🗣", "Coach", "checks in", "One question a day, chosen by what matters now."],
            ["🚨", "Escalator", "calls a human", "The only path to a clinical decision."],
          ].map(([glyph, name, verb, duty]) => (
            <div
              key={name}
              className="rounded-fam border border-fam-line bg-fam-surface p-5 shadow-fam"
            >
              <div className="flex items-baseline gap-2">
                <span className="text-lg">{glyph}</span>
                <span className="font-semibold text-fam-ink">{name}</span>
                <span className="text-xs text-fam-ink2">{verb}</span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-fam-ink2">{duty}</p>
            </div>
          ))}
        </div>

        <footer className="mt-16 border-t border-fam-line pt-6 text-xs text-fam-ink2">
          VitaHome never diagnoses and never prescribes. It executes instructions a
          licensed clinician already wrote — and hands every ambiguity to a human.
        </footer>
      </div>
    </main>
  );
}
