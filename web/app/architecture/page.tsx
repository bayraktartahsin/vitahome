import Link from "next/link";

/**
 * The architecture, drawn to be opened on camera.
 *
 * Two diagrams, because there are two things worth understanding and they are
 * different shapes:
 *
 *   1. how work flows — one synchronous parse, then everything else decoupled
 *      over Pub/Sub with per-agent attribute filters
 *   2. how work survives — the durability loop, which is the only part that
 *      makes the rest trustworthy
 *
 * Boxes-and-arrows diagrams of a microservice fan-out are interchangeable and
 * tell you nothing. The second diagram is the one that earns its space.
 */

export const metadata = {
  title: "VitaHome — architecture",
};

const INK = "#E8EAED";
const INK2 = "#8B94A3";
const LINE = "#2A313D";
const SURF = "#171C24";
const ACCENT = "#57A47B";
const WARN = "#D9A441";
const DANGER = "#D96C6C";
const INFO = "#6B9BD1";
const PURPLE = "#9B7BD1";

export default function Architecture() {
  return (
    <main className="theme-console min-h-screen">
      <div className="border-b border-con-line px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between text-xs">
          <Link href="/" className="text-con-ink2 hover:text-con-ink">
            ← VitaHome
          </Link>
          <div className="font-mono text-con-ink2">architecture</div>
          <Link href="/console" className="text-con-ink2 hover:text-con-ink">
            console →
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 py-10">
        <h1 className="font-display text-2xl text-con-ink">How the fleet is wired</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-con-ink2">
          One synchronous call — the parse, because a human is standing there holding a
          phone. Everything after it is decoupled: agents address each other by Pub/Sub
          attribute, never by function call. Moving any agent to its own Cloud Run service
          is a push-endpoint change, not a refactor.
        </p>

        <div className="mt-8 overflow-x-auto rounded-con border border-con-line bg-con-bg p-4">
          <FlowDiagram />
        </div>

        <h2 className="mt-14 font-display text-2xl text-con-ink">
          How a task survives its worker dying
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-con-ink2">
          This is the part that matters. Recovery is infrastructure, not choreography —
          nothing catches the kill, and no supervisor restarts anything. The message was
          never acked, so it comes back; the ledger already knows which steps happened.
        </p>

        <div className="mt-8 overflow-x-auto rounded-con border border-con-line bg-con-bg p-4">
          <DurabilityDiagram />
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          <Note title="Why the side effect is outside the transaction">
            Firestore transactions retry. Retrying a booking double-books a patient. So the
            effect runs first, and the record of it is committed transactionally afterwards
            with a re-check. The gap between those two is covered by writing the same
            idempotency key into the external system.
          </Note>
          <Note title="Why there is no exactly-once">
            There isn&rsquo;t one, in any distributed system, and claiming it would be the
            fastest way to lose a technical reviewer. At-least-once delivery plus idempotent
            steps gives effectively-once execution, which is the real thing.
          </Note>
          <Note title="Why retries cannot mask a bug">
            A task that fails deterministically would retry forever and starve the fleet, so
            after five attempts it is dead-lettered to the human queue and acked. Retries
            recover from crashes; they are not allowed to hide defects.
          </Note>
          <Note title="Why PHI never rides the queue">
            Pub/Sub messages carry references — a patient id and a task id. Each agent
            fetches what it needs inside its own IAM scope. The queue is not a place
            clinical data has to be trusted.
          </Note>
        </div>

        <p className="mt-10 font-mono text-[11px] text-con-ink2">
          Google Cloud Run · Pub/Sub · Firestore · Cloud Healthcare API (FHIR R4) · Cloud
          Scheduler · Secret Manager · Gemini 3.5 Flash-Lite &amp; 3.7 Flash · Agent
          Development Kit
        </p>
      </div>
    </main>
  );
}

function Note({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-con border border-con-line bg-con-surface p-4">
      <div className="text-sm font-semibold text-con-ink">{title}</div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-con-ink2">{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ flow -- */

function Box({
  x, y, w = 150, h = 44, label, sub, stroke = LINE, fill = SURF, text = INK,
}: {
  x: number; y: number; w?: number; h?: number;
  label: string; sub?: string; stroke?: string; fill?: string; text?: string;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8} fill={fill} stroke={stroke} />
      <text x={x + w / 2} y={sub ? y + h / 2 - 3 : y + h / 2 + 4}
            textAnchor="middle" fontSize="12.5" fill={text} fontWeight="600">
        {label}
      </text>
      {sub && (
        <text x={x + w / 2} y={y + h / 2 + 13} textAnchor="middle"
              fontSize="10" fill={INK2} fontFamily="ui-monospace, monospace">
          {sub}
        </text>
      )}
    </g>
  );
}

function Arrow({
  x1, y1, x2, y2, label, color = INK2, dashed = false,
}: {
  x1: number; y1: number; x2: number; y2: number;
  label?: string; color?: string; dashed?: boolean;
}) {
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth="1.4"
            strokeDasharray={dashed ? "4 3" : undefined} markerEnd="url(#arrow)" />
      {label && (
        <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} textAnchor="middle"
              fontSize="10" fill={color} fontFamily="ui-monospace, monospace">
          {label}
        </text>
      )}
    </g>
  );
}

function Defs() {
  return (
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill={INK2} />
      </marker>
    </defs>
  );
}

const AGENTS: [string, string, string][] = [
  ["Reconciler", "reconciler", PURPLE],
  ["Scheduler", "scheduler", ACCENT],
  ["Pharmacist", "pharmacist", "#D1A15B"],
  ["Watchman", "watchman", WARN],
  ["Coach", "coach", "#C97B4A"],
  ["Escalator", "escalator", DANGER],
];

function FlowDiagram() {
  return (
    <svg viewBox="0 0 1000 580" className="w-full min-w-[860px]"
         role="img" aria-label="VitaHome request flow architecture">
      <Defs />

      <Box x={20} y={30} w={170} h={52} label="Family surface" sub="/capture · Next.js" />
      <Arrow x1={190} y1={56} x2={268} y2={56} label="photo" />
      <Box x={270} y={22} w={200} h={68} label="Parser" sub="synchronous · ~3s"
           stroke={INFO} />
      <text x={370} y={106} textAnchor="middle" fontSize="10" fill={INK2}>
        the only synchronous call in the system
      </text>

      <Arrow x1={370} y1={116} x2={370} y2={152} label="care plan" />
      <Box x={280} y={154} w={180} h={44} label="dispatch" sub="publish + attribute" />

      <Arrow x1={370} y1={198} x2={370} y2={230} />
      <Box x={250} y={232} w={240} h={50} label="Pub/Sub · fleet-work" sub="one topic"
           stroke={ACCENT} />

      {/* fan-out */}
      {AGENTS.map(([name, slug, color], i) => {
        const y = 326 + i * 40;
        return (
          <g key={slug}>
            <path d={`M 370 282 C 370 ${304 + i * 4}, ${560} ${304 + i * 4}, 600 ${y + 15}`}
                  fill="none" stroke={LINE} strokeWidth="1.2" markerEnd="url(#arrow)" />
            <rect x={604} y={y} width={132} height={30} rx={6} fill={SURF} stroke={color}
                  strokeOpacity="0.5" />
            <text x={670} y={y + 19} textAnchor="middle" fontSize="12" fill={INK}>
              {name}
            </text>
            <text x={752} y={y + 19} fontSize="9.5" fill={INK2}
                  fontFamily="ui-monospace, monospace">
              agent = &ldquo;{slug}&rdquo;
            </text>
          </g>
        );
      })}
      <text x={670} y={312} textAnchor="middle" fontSize="10" fill={INK2}>
        six push subscriptions, separated by attribute filter
      </text>

      {/* stores */}
      <Box x={30} y={256} w={200} h={58} label="Firestore" sub="fleet state · task ledger"
           stroke={INFO} />
      <Box x={30} y={334} w={200} h={58} label="Firestore · audit" sub="append-only"
           stroke={INFO} />
      <Box x={30} y={412} w={200} h={58} label="Cloud Healthcare API"
           sub="FHIR R4 · real writes" stroke={ACCENT} />
      <Box x={30} y={490} w={200} h={44} label="Cloud Scheduler" sub="stale-lease sweep" />

      <Arrow x1={598} y1={446} x2={240} y2={446} color={LINE} />
      <text x={420} y={438} textAnchor="middle" fontSize="10" fill={INK2}
            fontFamily="ui-monospace, monospace">
        each agent reads PHI in its own IAM scope
      </text>

      <text x={560} y={566} textAnchor="middle" fontSize="10.5" fill={INK2}>
        messages carry a patient reference and a task id — never clinical content
      </text>
    </svg>
  );
}

/* ------------------------------------------------------------ durability -- */

function DurabilityDiagram() {
  const rowY = 96;
  const steps: [string, string, string][] = [
    ["1 · resolve_provider", "t_ab12:resolve_provider", ACCENT],
    ["2 · fhir_appointment", "t_ab12:fhir_appointment", ACCENT],
    ["3 · confirm", "t_ab12:confirm", ACCENT],
  ];

  return (
    <svg viewBox="0 0 1000 470" className="w-full min-w-[860px]"
         role="img" aria-label="How a task survives its worker being killed">
      <Defs />

      {/* attempt 1 */}
      <text x={20} y={40} fontSize="12" fill={INK2} fontFamily="ui-monospace, monospace">
        attempt 1
      </text>
      <rect x={20} y={54} width={620} height={76} rx={8} fill={SURF} stroke={LINE} />
      <text x={36} y={76} fontSize="11" fill={INK2}>worker A leases the task</text>

      {steps.map(([label, key, color], i) => {
        const x = 36 + i * 196;
        const dead = i > 0;
        return (
          <g key={key}>
            <rect x={x} y={rowY - 8} width={176} height={30} rx={6}
                  fill={dead ? "transparent" : "rgba(87,164,123,0.12)"}
                  stroke={dead ? LINE : color} strokeDasharray={dead ? "3 3" : undefined} />
            <text x={x + 88} y={rowY + 11} textAnchor="middle" fontSize="11"
                  fill={dead ? INK2 : INK}>
              {dead ? "never ran" : label}
            </text>
          </g>
        );
      })}

      {/* the kill */}
      <line x1={232} y1={46} x2={232} y2={140} stroke={DANGER} strokeWidth="2"
            strokeDasharray="5 4" />
      <text x={244} y={44} fontSize="12" fill={DANGER} fontWeight="600">
        os._exit(1) — mid-step, no cleanup
      </text>

      <rect x={660} y={54} width={320} height={76} rx={8} fill="rgba(217,108,108,0.08)"
            stroke={DANGER} strokeOpacity="0.4" />
      <text x={676} y={78} fontSize="11.5" fill={DANGER} fontWeight="600">
        message never acked
      </text>
      <text x={676} y={98} fontSize="10.5" fill={INK2}>
        no exception handler ran. no graceful
      </text>
      <text x={676} y={114} fontSize="10.5" fill={INK2}>
        shutdown. the process is simply gone.
      </text>

      {/* the gap */}
      <rect x={20} y={152} width={960} height={40} rx={6} fill="rgba(217,108,108,0.12)"
            stroke={DANGER} strokeOpacity="0.5" />
      <text x={36} y={177} fontSize="11.5" fill={DANGER}>
        AGENT_DOWN — the heartbeat goes stale. This gap stays in the audit trail permanently.
      </text>

      <Arrow x1={500} y1={196} x2={500} y2={222} color={WARN} label="Pub/Sub redelivers" />

      {/* attempt 2 */}
      <text x={20} y={246} fontSize="12" fill={INK2} fontFamily="ui-monospace, monospace">
        attempt 2
      </text>
      <rect x={20} y={260} width={620} height={76} rx={8} fill={SURF} stroke={ACCENT}
            strokeOpacity="0.4" />
      <text x={36} y={282} fontSize="11" fill={INK2}>
        worker B — a different process, on a fresh container
      </text>

      {steps.map(([label, , color], i) => {
        const x = 36 + i * 196;
        const skipped = i === 0;
        return (
          <g key={`b-${label}`}>
            <rect x={x} y={302} width={176} height={30} rx={6}
                  fill={skipped ? "rgba(107,155,209,0.12)" : "rgba(87,164,123,0.12)"}
                  stroke={skipped ? INFO : color} />
            <text x={x + 88} y={321} textAnchor="middle" fontSize="11" fill={INK}>
              {skipped ? "SKIPPED — already done" : label}
            </text>
          </g>
        );
      })}

      <rect x={660} y={260} width={320} height={76} rx={8} fill="rgba(87,164,123,0.08)"
            stroke={ACCENT} strokeOpacity="0.4" />
      <text x={676} y={284} fontSize="11.5" fill={ACCENT} fontWeight="600">
        one appointment. not two.
      </text>
      <text x={676} y={304} fontSize="10.5" fill={INK2}>
        the ledger knew step 1 had completed,
      </text>
      <text x={676} y={320} fontSize="10.5" fill={INK2}>
        so only the remaining work ran.
      </text>

      {/* the key */}
      <rect x={20} y={358} width={960} height={92} rx={8} fill={SURF} stroke={LINE} />
      <text x={36} y={382} fontSize="12" fill={INK} fontWeight="600">
        Why a replay cannot duplicate anything
      </text>
      <text x={36} y={404} fontSize="11" fill={INK2}>
        Every step&rsquo;s idempotency key is
        <tspan fill={INFO} fontFamily="ui-monospace, monospace"> {"{taskId}:{stepName}"}</tspan>
        — identical on every replay of that task.
      </text>
      <text x={36} y={422} fontSize="11" fill={INK2}>
        That key is also written INTO the external system, as the FHIR resource
        <tspan fill={INFO} fontFamily="ui-monospace, monospace"> identifier</tspan>, and every
        write searches for it first.
      </text>
      <text x={36} y={440} fontSize="11" fill={INK2}>
        So even a crash in the gap between &ldquo;appointment booked&rdquo; and &ldquo;we
        wrote down that we booked it&rdquo; still cannot book twice.
      </text>
    </svg>
  );
}
