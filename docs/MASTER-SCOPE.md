# 🏠 HOMEWARD — Master Scope v2 (post team-synthesis)

> *The hospital saves your life, then hands you a piece of paper. We take it from there.*

**Product:** Homeward — by Vitamedas Inc., from the makers of Vita
**Event:** All Things Agentic Hackathon (Google) · Track: **Fortified Enterprise Fleet** · also entering **Startup Excellence**
**Deadline:** Aug 31, 2026 5:00 PM PDT · submit **Aug 30** · 15 days from Aug 16
**Spoken positioning line:** *"the last mile of healthcare — the part nobody executes"*

v2 changes were produced by a five-specialist parallel review (judge simulation · narrative · pivot stress-test · win-probability model · architecture). Deltas from v1 marked ⚡.

---

## 1 · WHAT IT IS

An agent fleet that **executes medical instructions**. Photograph a discharge summary → the fleet parses it in ~1 second (catching the one instruction that kills if missed), reconciles medications, books every follow-up, routes prescriptions, arms monitoring for that document's specific red flags, runs voice check-ins, and escalates to a human clinician — **and refuses to act when instructions are ambiguous.** Full audit trail. Human-terminated escalation. A clinician console supervises 200 concurrent patient fleets.

**The thesis (⚡ new, from judge sim):** *calibrated non-autonomy.* In a regulated domain, the winning argument is not "look how much it does alone" — it's "look how precisely it knows when NOT to act alone." The fleet executes the mechanical; only licensed humans decide the clinical.

---

## 2 · THE EMOTIONAL CORE (⚡ locked by narrative + judge sim)

**The universal memory: the corridor.** Standing in a hospital hallway holding your PARENT's discharge papers, realizing you're now the responsible adult. Every judge 35+ has lived it; every judge under 35 dreads it. The judge simulation independently confirmed: *"my father had a stent in 2019… my mother highlighting the packet… nobody booked the follow-up."*

**Demo protagonist:** the adult child, first person, honest. One personal beat, said once, flat. Distance folded into a single sentence ("I was in another country when my family got this document") — every immigrant engineer on the panel finishes the story themselves.

**The retold moment is the ticagrelor catch, not the Failure Drill.** The judge sim was explicit: he'd retell the fatal-line catch first. The demo opens with it.

**Anti-schmaltz rules (hard constraints):**
1. Emotion must be measurable — timers, live bookings, a ringing check-in. No music, no stock footage.
2. One personal line, delivered once, never repeated. Return only to the paper as a prop.
3. Fear must be specific and checkable — the 10-second challenge lets judges scare themselves.

---

## 3 · NAME

**VitaHome.** *(Decided. Overrules this section's earlier recommendation of "Homeward", which is retained below as the reasoning that was weighed and rejected.)*

The Vita prefix is deliberate: Vitamedas Inc. ships Vita, a live health product, and VitaHome is the aftercare arm of that family rather than a standalone hackathon artifact. A founder with a shipped product extending it is a stronger story than a founder with an unrelated new name — it converts the "is this a weekend project?" question into a roadmap answer. "The Last Mile" survives as the spoken architecture line.

The counter-argument, on the record: Vita-prefixed naming invites comparison with a prior entry by the same team. Mitigated by keeping the two products architecturally and narratively separate — different track, different thesis, no shared code. Alternatives considered: Homeward, Aftercare, Handoff.

---

## 4 · THE FLEET (unchanged roles, upgraded duties)

| Agent | Job | Model | ⚡ v2 duty |
|---|---|---|---|
| **Parser** | multimodal doc → structured plan + criticality ranking | gemini-3.7-flash (sync, in-gateway, ~1s) | confidence threshold → low-confidence lines route to exception queue, never guessed |
| **Reconciler** | new vs existing meds, interactions, stops | 3.7-flash | ⚡ **The Refusal**: on ambiguity, declines to execute and escalates — on camera |
| **Scheduler** | books all follow-ups | 3.5-flash-lite + tools | ⚡ real Google Calendar invites arriving on a real phone on camera |
| **Pharmacist** | routes scripts, dose schedule | 3.5-flash-lite + tools | ⚡ real email/transmission to a device visible in the room |
| **Watchman** | monitors THIS doc's red flags | 3.5-flash-lite | ⚡ fires a live threshold event DURING the demo (unscripted-feeling) |
| **Coach** | adaptive voice check-ins | 3.7-flash + Gemini TTS | in-app voice; no phone-modal (VitaCare echo avoided) |
| **Escalator** | human-terminated escalation | 3.7-flash | visible go/NO-go decisions — including deciding a human was *not* needed |

---

## 5 · ARCHITECTURE (⚡ per architect's brief — build exactly this)

```
                 ┌─────────────── Cloud Run ───────────────────────────┐
 Phone photo ─▶  │ [gateway]  FastAPI + ADK Runner (min-inst=1)        │
                 │   Parser in-process (sync ~1s wow moment)           │
                 │   fan-out ──▶ Pub/Sub "fleet-work"                  │
                 │ [workers]  one service, six push endpoints          │
                 │   /reconciler /scheduler /pharmacist                │
                 │   /watchman /coach /escalator                       │
                 │ [supervisor+ui] heartbeat watcher · audit UI · drill│
                 └─────────────────────────────────────────────────────┘
   Firestore: fleet state · task ledger (idempotencyKey steps) · audit
   Healthcare API FHIR R4: clinical truth (Synthea + hero patient)
   Pub/Sub "vitals-sim" ▶ watchman · Cloud Tasks: check-in timers
   Secret Manager · Cloud Trace/Logging (through Gemma redaction)
```

**Key decisions (locked):**
- **3 Cloud Run services, not 7.** Agents are Pub/Sub-decoupled logical units with per-agent service accounts. The decoupling argument: *"contracts are Pub/Sub messages + Firestore docs, not function calls — extraction to a dedicated service is a config change."*
- **ADK is the backbone.** A2A agent cards served from `/registry` — satisfies the track's "agent registry" requirement *literally, at a URL*.
- **Raw GenAI SDK inside the Parser only** (structured output, thinking budget 0, speed).
- **Antigravity SDK: one timeboxed day** for the Coach; cut without guilt; note the evaluation in the README.
- **Firestore task ledger with idempotencyKey steps** = the replay log. FHIR writes carry the same key as an identifier → double-booking is impossible even mid-crash.
- **PHI never rides Pub/Sub** — messages carry FHIR references; agents fetch inside their own IAM scope.
- **⚡ Gemma 4's real job: PHI-redaction sidecar** — every log/trace line passes through Gemma before Cloud Logging. Real compliance-aware data handling, not a gimmick checkbox.
- **⚡ Lyria: cut.** If asked: "we chose not to bolt music onto a medical product." That answer earns respect.
- **⚡ Veo: pre-generated only** (personalized med-instruction clips rendered the night before, served from GCS). Never generated live.
- **⚡ A2A multi-institution handoff: CUT** from the build (ranked #8 of 9 in marginal-gain-per-day; 4–6 days for value judges can't distinguish in a 4-minute window). Registry cards remain A2A-native, so the protocol claim stays honest.

---

## 6 · THE FAILURE DRILL (⚡ now judge-driven — "the difference between $5K and $50K")

Not scripted. **The judge holds the knife.**

- **Two triggers, both real `os._exit(1)`.** `/chaos/arm` marks an agent to die inside its next step — the worker kills itself from within the step, before the side effect. `/chaos/kill` terminates whichever instance serves the request. ⚡ **Arm is the demo instrument**: hand-timed kills on Cloud Run land on an idle instance roughly half the time, which was observed live twice and is fatal on camera. Arming is deterministic and no less honest — the process still dies ungracefully, mid-step, with the message unacked. `DRILL_SLOW_SECONDS` additionally widens the window on one named step.
- ⚡ **Pub/Sub `ackDeadline` is 90s**, above the slowest real task. Set too low and a still-running task gets a spurious redelivery: survivable (every step skips) but it inflates the attempt counter and invites a question you do not want mid-demo.
- **Recovery is infrastructure, honestly:** Pub/Sub redelivery re-pushes the work; Cloud Run respawns the container. The supervisor doesn't respawn anything — **it narrates**: detects the stale heartbeat, writes `AGENT_DOWN` to the audit stream, and the UI shows the red gap → redelivery → steps 1–2 SKIPPED (idempotent) → step 3 executed → done.
- In the live demo: *invite the judge to pick which agent dies, and when.* Show the Firestore doc before/after.
- Rehearsed 20+ times. Must be boring by demo day.

## 6b · THE ADVERSARIAL INTAKE (⚡ judge sim's second demand)

Invite judges to hand the fleet **their own** discharge summary / any messy medical document, live. The win condition is not perfect parsing — it's that ambiguity routes to the clinician exception queue instead of hallucinated execution. *Declared behavior: "the fleet would rather ask than guess."*

## 6c · THE AUTONOMY LEDGER (⚡ verifiable counts only)

Live on-screen: `23 autonomous actions · 2 escalated to humans · 1 refused (ambiguous) · real external systems touched: 4`. **No dollar figures** — the judge sim called invented dollars "stagecraft arithmetic." Verifiable counts only. The "refused" counter is the thesis rendered as a number.

## 6d · REAL ACTION SURFACES (⚡ pivot explorer's hidden-risk fix)

FHIR fixes the record surface, not the action surface. "What did the Scheduler actually call?" must have a proud answer:
- Google Calendar API → **real invite arrives on a real phone, on camera**
- Real email transmission → arrives on a device in the room
- Healthcare API FHIR store → real writes, real Google Cloud service
- The one simulated endpoint (clinic EHR) wears an **honest on-screen badge**: "SMART-on-FHIR sandbox"
- Judges forgive declared simulation. They never forgive discovered simulation.

---

## 7 · THE 4-MINUTE LIVE DEMO (⚡ full arc, narrative-approved)

| Time | Beat |
|---|---|
| 0:00 | **The 10-second challenge.** Hold up the paper: "Eleven instructions. One kills him if missed. Find it — you have ten seconds." Silence. Then flat: "It took me three readings. If you've ever stood in a corridor holding your parent's paperwork, you know. I was in another country when my family got this one." |
| 0:30 | **The photo.** Live. Parser flags DO-NOT-STOP-ticagrelor in ~1s, ranked deadliest. "The fleet took one second." |
| 1:00 | **Execution, counted aloud.** Reconciliation → **The Refusal** (one ambiguous instruction escalated, on principle) → three bookings land → **a real calendar invite buzzes a real phone on camera** → scripts routed → monitoring armed. "Nobody typed anything. There is no chat window." |
| 2:00 | **The Failure Drill — judge's choice.** "Pick an agent. Kill it whenever you like." Red gap in the audit stream → redelivery → idempotent replay → completed. Firestore doc shown before/after. |
| 2:45 | **The live event.** Watchman threshold crosses mid-demo → Escalator's visible decision → clinician console lights up. Then the counter-beat: a second event where the Escalator decides a human was *not* needed. Restraint, visible. |
| 3:20 | **Scale + generality.** Console: 200 fleets, exception queue, SLA timers. Coda: photograph a pediatric vaccine sheet — same fleet ingests it. 15 seconds. |
| 3:45 | **Return to the paper.** Hold it up. *"The hospital saves your life, then hands you a piece of paper. We take it from there."* Stop talking. |

---

## 8 · 15-DAY BUILD ORDER (⚡ drill-first, per architect)

| Days | Work | Exit criteria |
|---|---|---|
| **1–3** | Firestore task ledger + idempotent step executor + Pub/Sub topology + Scheduler end-to-end + **first deploy** | public URL; one agent survives kill-and-replay locally |
| **4–5** | **Failure Drill + supervisor + audit stream UI** | drill works deployed, 10 consecutive clean runs |
| **6–9** | Parser (multimodal) · Reconciler + Refusal · Watchman · Escalator · Healthcare API FHIR (Synthea + hero patient) | Flow A end-to-end live |
| **10–11** | Coach (TTS) · Pharmacist · `/registry` A2A cards · Gemma redaction sidecar · clinician console + 200-fleet viz | Flows B/C live |
| **12–13** | Veo pre-gen clips · Autonomy Ledger · UI polish · `setup.sh` reproducibility · six ruthless audits | audit 100% green |
| **14–15** | **Rehearsal only.** Drill ×20 · adversarial docs ×10 · two full recorded takes | demo is boring-reliable |

**Degrade path:** behind 1d → cut Antigravity eval · 2d → cut Veo · 3d → cut Coach voice adaptivity · 4d → console scale-viz becomes static. **Never cut:** the step ledger, the drill, the audit UI, the live document flow. ("They're the scored substance.")

---

## 9 · HONEST ODDS (⚡ quant model, post-upgrade)

Real field: ~220–320 eligible submissions (5–10% Devpost conversion), ~40–60 complete. Likely **2–3 serious healthcare entries; plausibly the only one writing real FHIR.**

| Outcome | Probability |
|---|---|
| Grand Prize $50K | **~10–15%** (ceiling for anyone ≈ 25–30%; single-winner variance dominates) |
| ≥ $20K (grand ∪ Fleet track ∪ Startup Excellence) | **~40–45%** |
| ≥ 1 prize | **~55–60%** |

Startup Excellence is the quiet edge: eligible pool plausibly 15–30 entries → ~30–40% on that prize alone. Judge-sim deliberation result: 91/100, top-3 of forty; favored 60/40 in the final head-to-head *if* the real-action-surface criticism is closed (it now is, §6d).

**The "85%" reframe:** 85% is achievable on *winning something meaningful* only if we define it as ≥1 prize and execute the full package flawlessly plus bonus content (blog + hashtag + all rehearsals). No honest model puts a single-winner grand above ~15% for us or ~30% for anyone.

---

## 10 · MANDATORY & BONUS COMPLIANCE

- ✅ Gemini 3.5+ (3.7-flash, 3.5-flash-lite — verified on key)
- ✅ Google agent framework: **ADK** (+ Antigravity evaluated, documented)
- ✅ Google Cloud infra: Cloud Run · Firestore · Pub/Sub · Cloud Tasks · **Healthcare API** · Secret Manager · Cloud Trace
- ✅ Bonus models: **Gemma** (PHI redaction — real job) · **Veo** (pre-gen instruction clips) · Lyria intentionally declined
- ✅ Bonus content: build-blog + `#AllThingsAgenticHackathon` post (day 13, pre-written)
- ✅ Live unedited demo · reproducible `setup.sh` · Cloud console shown on camera

---

## 11 · JUDGE Q&A CARD (rehearse these)

1. *Agent dies between FHIR write and Firestore commit?* → replay re-runs the step; FHIR identifier search makes the write idempotent. No double-booking.
2. *Why not one service per agent?* → contracts are Pub/Sub + Firestore, not calls; extraction is config. Blast-radius pragmatism over deploy sprawl.
3. *Exactly-once?* → doesn't exist. At-least-once + idempotent steps = effectively-once.
4. *PHI governance?* → PHI only in FHIR/Firestore; messages carry references; logs pass Gemma redaction; per-agent IAM.
5. *What if Gemini misses the ticagrelor line?* → criticality-tagged structured output validated against a rule list; low confidence routes to the human queue. The fleet is human-terminated by design.
6. *What did the Scheduler actually call?* → Google Calendar API — the invite on this phone. FHIR Appointment — in Google's Healthcare API. The clinic EHR is a declared SMART-on-FHIR sandbox, badge on screen.
