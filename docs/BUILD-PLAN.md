# 🏠 VITAHOME — The Complete Build Plan
### Design · Mechanics · UI/UX · Engineering · 15 Days

> Working name **VitaHome** (find-replace safe if renamed). Companion doc: `MASTER-SCOPE.md` (strategy, odds, demo arc). This file is the execution bible — written to survive model/context switches. If you are an AI assistant reading this fresh: read `MASTER-SCOPE.md` first, then this, then start at the current day in §9.

---

# PART I — BRAND & DESIGN SYSTEM

## 1.1 The design thesis

Two surfaces, two temperatures, one system:

- **The Family side is WARM LIGHT.** Cream, sage, soft shadows. This is a kitchen-table product used by frightened people. It must feel like a calm competent relative, not software.
- **The Clinician Console is DENSE DARK.** Slate, monospace data, high information density. This is an ops room.
- The contrast IS the story: *"warm where families live, dense where clinicians work."* One accent family ties them together so they read as one product on camera.

This deliberately breaks from VitaCare's dark cyber look — different product, different soul, zero reskin echo.

## 1.2 Design tokens

```css
/* ============ FAMILY SURFACE (light, warm) ============ */
--fam-bg:          #FAF7F2;   /* warm cream — never pure white */
--fam-surface:     #FFFFFF;   /* cards */
--fam-surface-2:   #F3EEE6;   /* recessed panels */
--fam-ink:         #26332B;   /* deep green-charcoal text */
--fam-ink-2:       #6B7A70;   /* secondary text */
--fam-line:        #E5DED2;   /* hairlines */
--fam-accent:      #3E7C59;   /* sage green — health, calm, "go" */
--fam-accent-soft: #E7F0EA;
--fam-warm:        #C97B4A;   /* terracotta — human moments, voice */
--fam-attn:        #B8860B;   /* amber — needs attention */
--fam-danger:      #A63D3D;   /* muted red — red-flags ONLY. Never decorative. */
--fam-radius:      16px;      /* generous, soft */
--fam-shadow:      0 2px 16px rgba(38,51,43,0.07);

/* ============ CONSOLE SURFACE (dark, dense) ============ */
--con-bg:        #10141A;
--con-surface:   #171C24;
--con-surface-2: #1E242E;
--con-ink:       #E8EAED;
--con-ink-2:     #8B94A3;
--con-line:      #2A313D;
--con-accent:    #57A47B;    /* same green family, brightened for dark */
--con-warn:      #D9A441;
--con-danger:    #D96C6C;
--con-info:      #6B9BD1;
--con-radius:    10px;       /* tighter than family side */

/* ============ SHARED ============ */
--agent-parser:     #6B9BD1;  /* blue    📄 */
--agent-reconciler: #9B7BD1;  /* violet  💊 */
--agent-scheduler:  #57A47B;  /* green   📅 */
--agent-pharmacist: #D1A15B;  /* gold    🏥 */
--agent-watchman:   #D9A441;  /* amber   👁 */
--agent-coach:      #C97B4A;  /* terra   🗣 */
--agent-escalator:  #D96C6C;  /* red     🚨 */
```

## 1.3 Typography

| Role | Font (Google Fonts) | Notes |
|---|---|---|
| Family display | **Fraunces** (soft serif, 560 weight) | headlines only — warmth, editorial trust |
| Family UI | **Inter** | body, buttons, labels |
| Console everything | **Inter** | 13–14px density |
| Data/mono (both) | **JetBrains Mono** | ledger counts, timestamps, FHIR ids, audit stream |

Scale: family 17/15/13 body-first with 28–40 Fraunces displays; console 13/12 with 20 section heads. Line-height generous on family (1.6), tight on console (1.4).

## 1.4 Motion language

Motion carries the product's meaning: **execution you can watch.**

| Signature | Spec |
|---|---|
| **The Deconstruction** (THE UI wow) | After parse: highlight sweeps across the photographed document line-by-line (staggered 60ms); each recognized instruction **lifts off the page** as a card (translateY -8px, scale 1.02, shadow bloom, 280ms ease-out) and flies to its lane (FLIP technique). The paper visually *becomes* the plan. |
| **Criticality reveal** | The deadliest line gets a 400ms pause, then a slow amber→red underline draw (1.2s) + card border pulse ×2. Never blinking. Gravity, not alarm. |
| **Ledger tick** | Counter increments with a single upward odometer roll (180ms) + a brief green tick that fades. No confetti — this is medicine. |
| **Task progression** | Cards move between lanes with FLIP transitions; the working agent's avatar gets a soft 1.4s breathing pulse. |
| **The Drill gap** | Audit stream: heartbeat rows in mono green; on kill, a **red gap block physically expands** between rows (height animates in) with a live `+0.0s` counter; on recovery, rows resume BELOW the gap — the gap stays visible forever. The scar is the proof. |
| **The Refusal** | Card flips 180° from "executing" to a bordered card: "⚖ Declined to act — sent to Dr. queue." Flip = deliberate decision, not failure. |
| **Escalation** | Console-side: exception row slides in from top with a 600ms amber left-border sweep + SLA timer starts counting up live. |

Rules: nothing bounces, nothing spins, no easing longer than 400ms except the two ceremony moments (criticality reveal, drill gap). Reduced-motion media query honored.

## 1.5 Iconography & agent identity

Each agent = color + emoji-glyph + name + one-line verb, used identically on both surfaces:

```
📄 Parser      "reads"      💊 Reconciler  "checks"
📅 Scheduler   "books"      🏥 Pharmacist  "sends"
👁 Watchman    "watches"    🗣 Coach       "checks in"
🚨 Escalator   "calls a human"
```

The Escalator's verb is the thesis in three words. It appears under its avatar everywhere.

---

# PART II — UX ARCHITECTURE

## 2.1 The surfaces & routes

```
FAMILY (mobile-first web, works from a phone camera)
  /            → Landing/demo entry (hero + live capture CTA)
  /capture     → Camera / drop-zone → parse moment
  /plan        → The Plan (deconstructed document)
  /today       → The One Thing (daily focus) + check-in
  /ledger      → Autonomy Ledger (human-readable feed)

CONSOLE (desktop web, dark)
  /console               → Fleet overview (200 patients)
  /console/patient/:id   → Patient fleet detail (runtimes + ledger + audit)
  /console/exceptions    → Exception queue (refusals + escalations) ← human-terminated surface
  /console/registry      → A2A agent cards, versions
  /console/drill         → Chaos panel (judges use this)

SHARED
  /pitch /diagram        → assets-as-routes (playbook pattern)
```

## 2.2 The two journeys

**Journey A — Sarah (caregiver, 34, another city).** Photographs dad's discharge summary → 1s parse → watches the Deconstruction → sees the fatal line flagged → taps "Let VitaHome take it" (single consent moment, explicit scope list) → watches the ledger fill: booked, sent, armed → gets ONE decision request (the Refusal: ambiguous line needs the doctor) → daily: opens /today, sees The One Thing, dad's check-in status.

**Journey B — Dr. Chen (clinician, on-call).** Console shows 200 fleets green/amber/red → exception queue has 2 items with SLA timers → opens Robert's refusal, reads the ambiguous line + the fleet's reasoning + source-line provenance → taps Resolve with a decision → fleet resumes instantly (visible on family side) → 2am: escalation fires, pager entry with full context pre-assembled: current meds, the red-flag match, trend chart, one-tap callback.

## 2.3 Information hierarchy law

Every screen answers, in order: **1) Is anything wrong? 2) What is being done right now? 3) What was done? 4) What needs ME?** Red-flag state trumps everything and restructures the screen when active.

---

# PART III — SCREEN SPECS

## 3.1 Family · /capture

- Full-bleed warm cream; centered Fraunces headline: *"Photograph the papers they gave you."* Sub: *"Discharge summaries · care plans · any medical instructions."*
- Camera viewport (or drop-zone on desktop) with soft corner brackets; live edge-detection glow when a document fills the frame.
- On capture: paper thumbnail freezes top-center → **parse progress is the document itself lighting up** line-by-line (no spinner ever) → 1.0s → count-up "11 instructions found" → **criticality reveal ceremony** (§1.4).
- Below fold after parse: `[ See the plan → ]` primary; `[ This looks wrong ]` ghost-link → exception intake (adversarial-doc path, always present).

## 3.2 Family · /plan — The Plan

The photographed document, deconstructed into four lanes (vertical scroll, sticky lane headers):

1. **⚠ The Critical Line** — pinned card, danger-bordered: the fatal instruction verbatim + plain-English *why* ("Stopping this early can cause a fatal clot in the new stent") + source-line thumbnail crop of the actual paper. Tap → full provenance.
2. **💊 Medications** — timeline strip (morning/noon/evening/night columns), each med a pill-chip with dose; STOPPED meds shown struck-through with "replaced by ▸"; interactions flagged by Reconciler with violet tag.
3. **📅 Appointments** — cards with live status chips: `finding time… → booked ✓ Tue 10:00 → invite on your phone ✓`. Each card shows the agent avatar that did it + timestamp + provenance link.
4. **🛟 Watching for** — the red-flag list as calm sentences ("Chest pain · trouble breathing at rest · bleeding") + "VitaHome watches for these 24/7. If one appears: a human clinician, immediately."
- Persistent footer bar: mini-ledger `23 done · 1 waiting on Dr. Chen · watching ✓` → taps to /ledger.

## 3.3 Family · /today — The One Thing

- Date + Fraunces greeting. One dominant card: **today's single most important action** ("First ticagrelor dose — 8:00 AM ☐"). Everything else collapsed below ("3 more today ▸").
- Check-in module: terracotta voice orb (🗣 Coach) — tap to talk or type; asks ONE adaptive question ("Any chest discomfort today?"); transcript renders as chat bubbles; answers feed Watchman.
- If a check-in answer matches a red-flag → screen state changes live: danger banner + "Dr. on-call has been paged — 00:41 ago" + callback status. (This is demo Flow B, on the family side.)

## 3.4 Family · /ledger — the Autonomy Ledger

- Top: four mono counters, odometer-rolling: `Autonomous actions 23 · Human decisions 2 · Declined (asked instead) 1 · Real systems touched 4`.
- Feed below, newest first, human sentences with agent avatars: *"📅 Booked cardiology follow-up — Tue Aug 26, 10:00 · invite sent to your phone"* … *"⚖ 💊 One instruction was ambiguous — asked Dr. Chen instead of guessing"*. Every row: timestamp + provenance chip (`line 7 of your document`) + (where real) external proof chip (`Google Calendar ↗`).
- No dollars anywhere. Counts only. (Judge-sim mandate.)

## 3.5 Console · /console — Fleet overview

- Header strip: `212 active fleets · 3 exceptions · 1 escalation · p95 task latency 2.1s` (live).
- Grid of patient cells (virtualized): name, condition tag, fleet-state dot (green working / amber exception / red escalation / gray tapering), sparkline of last-24h activity, SLA badge if waiting on human.
- Sort defaults to "needs attention first." One click → patient detail. This grid at 200 rows IS demo Flow C's money shot.

## 3.6 Console · /console/patient/:id — Fleet detail

Three columns:
1. **Runtimes** — 7 agent cards: state (idle/working/leased/down), current task, heartbeat age (mono, ticking), version from registry. During the Drill, Scheduler's card goes red `DOWN — no heartbeat 4.2s` live.
2. **Task ledger** — the Firestore ledger rendered: tasks with step chips (`step 1 ✓ · step 2 ✓ · step 3 …`), idempotency keys on hover, refusals flagged violet.
3. **Audit stream** — mono, append-only, auto-scrolling; heartbeats, actions, A2A registry lookups, **the drill gap block** (§1.4). Filter chips: all / actions / failures / access.

## 3.7 Console · /console/exceptions — the human-terminated surface

- Queue rows: patient · type (Refusal ⚖ / Escalation 🚨) · the ambiguous/triggering content verbatim · fleet's reasoning ("two plausible readings: 'resume ALL home meds' conflicts with STOP amlodipine on line 4") · source-line image crop · **SLA timer counting up** · `[ Resolve ▸ ]`.
- Resolve panel: radio decision options the fleet prepared + free-text override + signature line "Decided by Dr. Chen · logged". On resolve: row collapses with green sweep; family side updates within 1s (demo this round-trip!).
- Empty state: *"Nothing needs a human right now. The fleet knows where you are."*

## 3.8 Console · /registry & /drill

- **Registry:** A2A agent cards as formatted JSON panels — name, version, capabilities, IAM scope, model, instruction hash. Header: `GET /registry — live A2A agent cards`. (Track requirement, satisfied at a URL.)
- **Drill (chaos panel):** big red industrial toggle per agent: `KILL PROCESS` + "judges: pick any agent, any time." Below: last-drill replay summary (gap duration, steps skipped, steps re-run, external side-effects: 0 duplicates). This page is *handed to the judge* during the demo.

---

# PART IV — MECHANICS (contracts & schemas)

## 4.1 Task state machine

```
                    ┌────────── redelivery (Pub/Sub) ──────────┐
                    ▼                                          │
 pending ──▶ leased(agent, heartbeatAt, leaseExpiresAt) ──▶ [DEAD]
                    │
        ┌───────────┼──────────────┬─────────────────┐
        ▼           ▼              ▼                 ▼
   done(steps✓)  refused(reason) escalated(sla)  failed(err)
                    │              │                 │
                    └──────▶ exception queue ◀───────┘
                                   │ human resolves
                                   ▼
                            resumed → pending(next task)
```

## 4.2 Firestore schema (authoritative)

```
patients/{pid}
  profile        {name, dob, lang, caregiverContact}
  carePlan       {sourceDocGcsUri, parsedAt, parserVersion,
                  instructions: [{id, lineNo, cropUri, type, text,
                                  criticality: none|caution|CRITICAL,
                                  confidence, status}]}
  tasks/{taskId} {agent, instructionId, status, attempt,
                  leasedBy, heartbeatAt, leaseExpiresAt,
                  input,                       // full message copy
                  steps: [{name, idempotencyKey, // = taskId:stepName
                           result, externalRef, at}],
                  refusal: {reason, options[]} | null,
                  escalation: {trigger, slaStartedAt, resolvedBy} | null}
  audit/{seq}    {at, actor, kind: heartbeat|action|AGENT_DOWN|
                  redelivery|skip|refusal|escalation|access,
                  detail, taskId?}
  vitals/{ts}    {type, value, source: sim}     // Watchman input
ledger/{pid}     {autonomous, humanDecisions, refused, systemsTouched}
registry/agents/{agent}  {a2aCard, version, modelId, iamScope, instructionHash}
```

## 4.3 Event contracts (Pub/Sub, PHI-free — references only)

```jsonc
// topic: fleet-work  (push-subscribed per agent endpoint)
{ "taskId": "t_01J...", "patientRef": "patients/p_hero",
  "agent": "scheduler", "instructionRef": "carePlan/instructions/i_07",
  "attempt": 1, "traceId": "..." }

// topic: vitals-sim → /watchman
{ "patientRef": "patients/p_hero", "obsType": "chest_pain_report",
  "value": 1, "at": "2026-08-30T02:00:11Z" }
```

## 4.4 Agent I/O contracts

| Agent | Input | Steps (idempotent) | Output / side-effects |
|---|---|---|---|
| **Parser** (sync, gateway) | image/PDF | single call, structured output schema, thinking=0 | carePlan doc; per-instruction confidence; `<0.85` → status `needs_review` → exception |
| **Reconciler** | carePlan + FHIR MedicationRequest(active) | 1 fetch-existing · 2 analyze (3.7-flash) · 3 write DetectedIssue | interaction tags; ambiguity → `refused` + options for humans |
| **Scheduler** | instruction(followup) | 1 resolve provider · 2 create FHIR Appointment (identifier=idemKey, search-before-create) · 3 Google Calendar insert (real invite) · 4 ledger++ | booked status + externalRef both systems |
| **Pharmacist** | instruction(med) | 1 write MedicationRequest routing · 2 send real email (device on camera) · 3 dose schedule → /today | routed status |
| **Watchman** | vitals events + red-flag list | stateless eval per event (flash-lite); threshold match → publish escalation task | Observation writes; trigger events |
| **Coach** | daily Cloud Task timer | 1 compose question (context: recent vitals+answers) · 2 TTS audio · 3 record answer → vitals | check-in transcript |
| **Escalator** | escalation tasks | 1 assemble context pack · 2 decide notify-level (go/NO-go, logged either way) · 3 page + SLA start | exception row; Flag+Communication in FHIR |

## 4.5 The Drill — exact mechanics

1. `DRILL_SLOW=8` env → Scheduler sleeps 8s between steps 2→3 (the reliable kill window).
2. Judge presses KILL on /console/drill → `POST /chaos/kill?agent=scheduler` → `os._exit(1)`.
3. Detection layer 1 (recovery): Pub/Sub ack deadline 30s → redelivery. Layer 2 (narration): supervisor polls Firestore 5s for stale heartbeats → writes `AGENT_DOWN` audit event → UI gap block expands.
4. Redelivered task: transaction reads `steps[]` → steps 1–2 have idempotencyKeys present → SKIP (audit `skip` events) → step 3 executes → done. Calendar/FHIR search-by-identifier guarantees zero duplicate bookings even in the crash window.
5. Console shows: gap (red, duration) → redelivery → skips → completion. Family side: appointment card never regressed — it just completes. *That asymmetry is the design: families never see infrastructure pain.*

## 4.6 Demo-day live events

- Vitals simulator (Cloud Scheduler → Pub/Sub) runs a benign baseline; presenter has a hidden trigger (`POST /sim/event?type=chest_pain`) fired from a phone for Flow B — feels unscripted, is deterministic.
- The counter-beat: second trigger `?type=mild_fatigue` → Escalator decides NO human needed → logged visible restraint.

---

# PART V — ENGINEERING PLAN

## 5.1 File tree

```
vitahome/
├── backend/                    # Python 3.12 · FastAPI · ADK
│   ├── app/
│   │   ├── gateway/            # main.py, parser.py (sync), consent.py
│   │   ├── agents/             # reconciler.py scheduler.py pharmacist.py
│   │   │                       # watchman.py coach.py escalator.py (push endpoints)
│   │   ├── fleet/              # ledger.py (step executor, idempotency)
│   │   │                       # supervisor.py registry.py chaos.py
│   │   ├── integrations/       # fhir.py gcal.py email.py tts.py veo.py gemma_redact.py
│   │   ├── sim/                # vitals.py seed_synthea.py hero_patient.py
│   │   └── config.py llm.py
│   ├── tests/                  # ledger idempotency · refusal policy · drill replay ·
│   │                           # parser criticality · escalator go/no-go
│   ├── Dockerfile  pyproject.toml  .dockerignore
├── web/                        # Next.js 14 · two theme roots
│   ├── app/(family)/ capture plan today ledger
│   ├── app/console/  page patient/[id] exceptions registry drill
│   ├── app/pitch app/diagram
│   ├── components/family/      # DocumentCapture DeconstructionCanvas CriticalCard
│   │                           # MedTimeline ApptCard LedgerFeed VoiceOrb OneThing
│   ├── components/console/     # FleetGrid RuntimeCard TaskLedger AuditStream
│   │                           # GapBlock ExceptionRow SlaTimer DrillPanel RegistryCard
│   └── lib/sse.ts theme.ts
├── infra/setup.sh              # ONE script: APIs, FHIR store, topics, deploy (reproducibility req)
└── docs/                       # MASTER-SCOPE BUILD-PLAN demo-script video assets blog draft
```

## 5.2 Playbook pre-flight (bugs we refuse to repeat)

`.dockerignore` before first build · README.md in Docker COPY · `/health`+`/healthz` both · secrets in Secret Manager only · `min-instances=1` all services · StrictMode off · API URL by runtime hostname check · **SSE never proxied through Next** · `"use client"` on interactive pages · git noreply email from commit #1 · no AI trailers ever · ADK names = valid identifiers · measure latency before model choices (done: flash-lite 1.03s, 3.7-flash 2.35s).

## 5.3 Testing gates

- **pytest (~25):** step-executor idempotency (kill between every step pair) · refusal on ambiguity fixtures · parser criticality on 10 doc fixtures (incl. the hero ticagrelor doc + 3 adversarial messes) · escalator go/no-go matrix · PHI-free event payloads (schema assert).
- **Playwright suite:** full Flow A on deployed URL · drill via API-kill with gap-assert · exception resolve round-trip → family update · mobile viewports (390px) · zero console errors.
- **The demo gate:** 10 consecutive clean full-demo runs on the deployed URL before any recording. Non-negotiable.

## 5.4 Day-by-day (15 days, deliverable-gated)

| Day | Build | Gate |
|---|---|---|
| **1** | repo (noreply email) · GCP project · APIs (incl. **Healthcare API**) · Firestore · topics · Secret Manager · skeleton all-stubs · `setup.sh` v0 · **deploy all 3 services** | public URLs healthy |
| **2** | task ledger + step executor + idempotency · Scheduler end-to-end (FHIR appt + real GCal invite) | kill-replay clean locally ×5 |
| **3** | supervisor + audit stream + heartbeats · deploy | drill works ON CLOUD RUN |
| **4** | /console/drill panel + GapBlock UI + audit UI live | judge-drill demoable, ugly |
| **5** | Parser sync path: capture → structured carePlan (hero doc) · confidence routing | photo→plan on deployed URL |
| **6** | **Deconstruction animation** + criticality ceremony + /plan lanes | THE UI wow works on a phone |
| **7** | Reconciler + **Refusal** mechanics + exceptions queue + resolve round-trip | Flow: refusal → Dr. resolves → family updates |
| **8** | Watchman + vitals sim + Escalator + context pack + SLA timers | Flow B live incl. restraint counter-beat |
| **9** | Pharmacist (real email) + /today + One Thing + dose schedule | buffer ½ day |
| **10** | Coach: TTS check-in + voice orb + transcript→vitals · Cloud Tasks timers | daily loop closes |
| **11** | Fleet overview 200-fleet grid (seed 200 Synthea-based fleets) + registry page + A2A cards endpoint | Flow C money shot |
| **12** | Autonomy Ledger (counters+feed+provenance chips) · Gemma redaction sidecar · consent screen | compliance scene demoable |
| **13** | Veo pre-gen clips · polish pass · **six ruthless audits** (playbook §04) · fix · redeploy · blog draft + social draft | full-stack audit 100% green |
| **14** | **Rehearsal day 1:** drill ×20 · adversarial docs ×10 · full demo ×5 · fix flow bumps only | demo boring-reliable |
| **15** (Aug 30) | **Rehearsal day 2 + record two full live takes** · submission copy · diagram+pitch export · **SUBMIT** · publish blog+hashtag post | submitted 24h early |

Degrade path & never-cut list: per MASTER-SCOPE §8. Antigravity eval only if a day is gained, never spent.

## 5.5 Definition of done (submission)

☐ Live URL: full Flow A from a stranger's phone ☐ judge-drill from /console/drill ☐ exception round-trip <1s ☐ 200-fleet console ☐ `setup.sh` recreates env from zero (tested once in a fresh project) ☐ ~4-min live unedited video with Cloud console shown ☐ architecture diagram ☐ README spin-up ☐ blog + hashtag post ☐ repo history clean (no AI fingerprints, noreply email) ☐ pytest+Playwright green in CI ☐ ledger counters truthful and auditable.

---

*Demo choreography, judge Q&A card, odds model, and emotional arc live in `MASTER-SCOPE.md`. Build starts at §5.4 Day 1.*
