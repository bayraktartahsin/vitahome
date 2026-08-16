import Link from "next/link";

/** Clinician console — dense dark. An ops room. */
export default function Console() {
  return (
    <main className="theme-console min-h-screen">
      <div className="border-b border-con-line px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between text-xs">
          <Link href="/" className="text-con-ink2 hover:text-con-ink">
            ← VitaHome
          </Link>
          <div className="font-mono text-con-ink2">
            clinician console · fleet supervision
          </div>
          <Link href="/console/drill" className="text-con-danger hover:underline">
            chaos panel
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-wrap gap-6 font-mono text-xs text-con-ink2">
          <span>
            <span className="text-con-ink">—</span> active fleets
          </span>
          <span>
            <span className="text-con-warn">—</span> exceptions
          </span>
          <span>
            <span className="text-con-danger">—</span> escalations
          </span>
          <span>
            p95 task latency <span className="text-con-ink">—</span>
          </span>
        </div>

        <div className="mt-8 rounded-con border border-dashed border-con-line p-12 text-center">
          <div className="font-mono text-sm text-con-ink2">
            fleet grid · patient runtimes · audit stream
          </div>
          <div className="mt-2 text-xs text-con-ink2/70">
            wiring lands day 11 — see docs/BUILD-PLAN.md §5.4
          </div>
        </div>
      </div>
    </main>
  );
}
