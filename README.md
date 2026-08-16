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
| 📄 | **Parser** | reads | Document → structured plan; ranks each instruction by how dangerous it is to miss |
| 💊 | **Reconciler** | checks | New meds vs existing; interactions, duplications, what to stop |
| 📅 | **Scheduler** | books | Every follow-up appointment, autonomously |
| 🏥 | **Pharmacist** | sends | Routes prescriptions, builds the dose schedule |
| 👁 | **Watchman** | watches | The red flags named in *this* document, 24/7 |
| 🗣 | **Coach** | checks in | One adaptive question a day, by voice |
| 🚨 | **Escalator** | calls a human | The only path to a clinical decision |

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

Gemini 3.7 Flash · Gemini 3.5 Flash-Lite · Gemini TTS · **Gemma 4** (PHI redaction before logs) · **Veo 3.1** (personalised instruction clips) · Agent Development Kit · A2A agent cards · **Cloud Healthcare API (FHIR R4)** · Cloud Run · Firestore · Pub/Sub · Cloud Tasks · Cloud Scheduler · Secret Manager · Cloud Trace.

## Safety

VitaHome **never diagnoses and never prescribes.** It executes instructions a licensed clinician already wrote. Ambiguity is routed to a human, never guessed. Every action traces to the exact line of the source document that authorised it. PHI lives only in FHIR and Firestore — Pub/Sub messages carry references, and logs pass through Gemma redaction before reaching Cloud Logging. All demo patients are synthetic.

## Docs

- [`docs/MASTER-SCOPE.md`](docs/MASTER-SCOPE.md) — strategy, demo choreography, judge Q&A
- [`docs/BUILD-PLAN.md`](docs/BUILD-PLAN.md) — design system, UX specs, mechanics, 15-day plan

---

© 2026 Graviti Labs
