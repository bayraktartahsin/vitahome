# 🏠 VitaHome

> **The hospital saves your life, then hands you a piece of paper. We take it from there.**

An **agent fleet that executes medical instructions.** Photograph a discharge summary and the fleet reconciles the medications, books every follow-up, routes the prescriptions, arms monitoring for that document's specific red flags, checks in daily — and hands a licensed human every decision it should not make alone.

Built for the **All Things Agentic Hackathon** · track: **The Fortified Enterprise Fleet** · by [Graviti Labs](https://vitamedas.com), makers of Vita.

---

## Why

~20% of Medicare patients are readmitted within 30 days. $26B/yr of that is avoidable. Over 60% of post-discharge follow-ups are never booked. Almost none of this is a medical failure — the medicine was right. **Nobody executed it.**

## The fleet

| | Agent | Verb | Duty |
|---|---|---|---|
| Pa | **Parser** | reads | Document → structured plan; re-ranks every instruction by how dangerous it is to miss |
| Rc | **Reconciler** | checks | New meds vs. the FHIR record; finds contradictions and refuses to resolve them |
| Sc | **Scheduler** | books | Every follow-up appointment, autonomously, into a real FHIR store |
| Ph | **Pharmacist** | sends | Turns "twice daily for 12 months" into an actual clock; never invents a time |
| Wa | **Watchman** | watches | The red flags named in *this* document — nothing generic |
| Co | **Coach** | checks in | One question a day, chosen from what the fleet does not know |
| Es | **Escalator** | calls a human | The only path to a clinical decision — and the only agent that may decline |

All seven are live and published as A2A agent cards at [`/registry`](https://vitahome-gateway-205100594497.us-central1.run.app/registry).

**Four of them can refuse.** That is not a failure path. The Reconciler refuses a medication contradiction, the Pharmacist refuses a dosage it cannot schedule without guessing, the Coach declines to send a check-in with nothing to learn, and the Escalator declines to wake a clinician who is not needed. Each refusal hands a human a decision with the options already assembled.

**The thesis is calibrated non-autonomy.** In a regulated domain the interesting question isn't how much a fleet does alone — it's how precisely it knows when *not* to. VitaHome executes the mechanical and refuses the clinical.

## Architecture

```
 photo ─▶ [gateway]  FastAPI + ADK · Parser runs synchronously (~1s)
          │          fan-out ──▶ Pub/Sub "fleet-work"
          ▼
          [agents]   six push endpoints, one per agent, per-agent IAM scope
          [supervisor] heartbeat watch · AGENT_DOWN events · audit stream

 Firestore              fleet state · task ledger (idempotent steps) · audit
 Healthcare API (FHIR R4)  clinical source of truth — real writes, not mocks
 Pub/Sub · Cloud Tasks  async runtime · check-in timers
 Secret Manager · Cloud Trace
```

Agents communicate through **Pub/Sub messages and Firestore task documents — never direct function calls.** Extracting any agent to its own Cloud Run service is a routing change, not a refactor.

**Durability:** every side effect is a *step* with a deterministic idempotency key, recorded after it succeeds. Kill an agent mid-task and Pub/Sub redelivers; the replaying agent skips completed steps. External writes carry the same key into FHIR (`identifier`) and Calendar (`iCalUID`) with search-before-create, so even a crash between "effect done" and "step recorded" cannot duplicate. At-least-once delivery + idempotent steps = effectively-once. There is no exactly-once and we don't pretend there is.

## Live

| | |
|---|---|
| Web | https://vitahome-web-205100594497.us-central1.run.app |
| Gateway | https://vitahome-gateway-205100594497.us-central1.run.app |
| Fleet registry (A2A cards) | [`/registry`](https://vitahome-gateway-205100594497.us-central1.run.app/registry) |
| Substrate health | [`/health/deep`](https://vitahome-gateway-205100594497.us-central1.run.app/health/deep) |

## Track requirements, mapped to artifacts

Every Fortified Enterprise Fleet requirement, with the URL that proves it —
verify rather than trust:

| Requirement | Where it is, live |
|---|---|
| **Agent registry** | [`/registry`](https://vitahome-gateway-205100594497.us-central1.run.app/registry) — seven A2A cards, each naming its model, IAM scope, instruction hash, and **which Cloud Run service it runs on** |
| **Async runtime** | One Pub/Sub topic, one filtered push subscription per agent, supervised lifecycle with lease + heartbeat. The Scheduler runs on [its own Cloud Run service](https://vitahome-scheduler-205100594497.us-central1.run.app/health) — extracted with a push-endpoint change and zero code changes, which is the decoupling claim made checkable |
| **Persistent memory** | Firestore task ledger (idempotent step records that survive worker death — the [drill](https://vitahome-web-205100594497.us-central1.run.app/console/drill) is the proof), care plans, append-only audit trail, and the Cloud Healthcare API FHIR store as clinical source of truth |
| **Security & governance** | Model-advises/code-decides boundaries in every agent; the Escalator's one-way override; human-terminated escalations with SLA clocks; per-agent IAM scopes on the registry cards; `DEMO_KEY` lock for destructive endpoints (below) |
| **Compliance-aware data handling** | PHI never rides the queue (messages carry references; agents fetch in their own IAM scope); a deterministic redaction filter on every log record; and [Gemma auditing the logs](https://vitahome-gateway-205100594497.us-central1.run.app/compliance/redactions) to make the "no PHI in logs" claim falsifiable |

### Security posture, stated plainly

The demo endpoints (`/demo/*`, `/chaos/*`) are **open on purpose**: judges are
invited to kill agents and reseed patients themselves, and an auth wall would
end that. That is a deliberate, reversible choice, not an oversight — set the
`DEMO_KEY` env var and every destructive endpoint requires an `X-Demo-Key`
header, with no redeploy. Read paths and patient flows are unaffected either
way. What a production deployment would change is documented honestly: IAP in
front of the console, per-agent service accounts instead of the shared default,
and VPC-SC around the Healthcare API.

## Break it yourself

The interesting claim is not that it works. It is what happens when it doesn't.

```bash
./scripts/preflight.sh    # everything that must be green before a live run
./scripts/drill.sh        # arm an agent, kill it mid-step, watch it recover
./scripts/monitor.sh both # the escalation, then the decision NOT to escalate
```

**The Failure Drill.** `/chaos/arm` marks an agent to die inside its next step —
a real `os._exit(1)`, no cleanup, no graceful shutdown, message left unacked.
The Pub/Sub message is redelivered, Cloud Run supplies a fresh container (the
worker ID in the audit trail visibly changes), and the ledger skips every step
that already completed. One appointment. Not two.

Nothing here is choreographed. There is no exception handler catching the kill;
the process is simply gone. `/chaos/kill` is the immediate variant — it is
kept, but it is a poor demo instrument, because on Cloud Run the request often
lands on an instance that is not the one doing the work. Arming is deterministic
and no less violent.

The gap the dead worker leaves is never cleaned out of the audit trail. In a
regulated domain the scar is the evidence.

```
lease       leased by nj4·f7210a
AGENT_DOWN  killed mid-step 'resolve_provider' — process exiting without ack
redelivery  redelivered — attempt 2 (previous worker did not finish)
lease       leased by nj4·450f78          ← different process
skip        step 'resolve_provider' already completed — skipped on replay
```

**Retries do not mask bugs.** A deterministically-failing task would otherwise
retry forever and starve the fleet, so after five attempts it is dead-lettered
to the human queue and acked. That guard has already earned its place: a null
FHIR timestamp was caught by it during development instead of taking the service
down.

## Spin up from zero

```bash
git clone https://github.com/bayraktartahsin/vitahome && cd vitahome
export GEMINI_API_KEY=...            # from https://aistudio.google.com/apikey
./infra/setup.sh <YOUR_PROJECT_ID>   # idempotent; provisions everything and deploys
```

`setup.sh` enables the APIs, creates Firestore, the Healthcare dataset + FHIR R4 store, the Pub/Sub topics and push subscriptions, stores the secret, grants IAM, and deploys both services. Re-runnable.

### Local development

```bash
# backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # add GEMINI_API_KEY
uvicorn app.gateway.main:app --reload --port 8080

# web
cd web && npm install && npm run dev
```

## Google stack

**In use today:** Gemini 3.5 Flash-Lite (extraction) · Gemini 3.7 Flash (judgement) · Agent Development Kit · A2A agent cards · **Cloud Healthcare API (FHIR R4)** · Cloud Run · Firestore · Pub/Sub · Cloud Scheduler · Secret Manager · Cloud Build.

**Planned, not yet shipped:** Gemini TTS (the Coach asks in text today, not voice), Gemma 4 (PHI redaction before logs), Veo 3.1 (personalised instruction clips), Cloud Tasks, Cloud Trace. They are named here because they are on the roadmap, not because they are running.

Model tiers were chosen from measurements on this project's own prompts, not from a datasheet — Flash-Lite for structured extraction on the hot path, Flash for the two places the model is asked to exercise judgement (ambiguity, escalate-or-not), where the extra ~1.3s buys something.

## Safety

VitaHome **never diagnoses and never prescribes.** It executes instructions a licensed clinician already wrote. Ambiguity is routed to a human, never guessed. Every instruction carries the line number it came from, so any action can be checked against the paper in your hand.

**The model advises; only code decides.** Gemini flags a medication contradiction — a deterministic branch decides whether that becomes an action or a refusal, and a flagged drug can never be written even if the model also emits a change for it. The Escalator may be overruled by code in exactly one direction: toward paging, never away from it. A model's reassurance cannot suppress a symptom printed on the patient's own return-to-emergency list.

PHI lives only in FHIR and Firestore. Pub/Sub messages carry references, and each agent fetches what it needs inside its own IAM scope. All demo patients are synthetic; there is no real patient data anywhere in this project.

### What is simulated, stated plainly

- **the provider directory** the Scheduler picks from (labelled "provider directory (demo)" in every response)
- **the home-monitoring feed** — there is no wearable; the reports in `app/sim/vitals.py` are written as a family member would actually send them, and every response is tagged `simulated home monitor`

Everything else touches a real Google Cloud service. FHIR Patients, Appointments, MedicationRequests and Observations are genuine writes to a managed Healthcare API store.

## Docs

- [`docs/MASTER-SCOPE.md`](docs/MASTER-SCOPE.md) — strategy, demo choreography, judge Q&A
- [`docs/BUILD-PLAN.md`](docs/BUILD-PLAN.md) — design system, UX specs, mechanics, 15-day plan

---

© 2026 Graviti Labs
