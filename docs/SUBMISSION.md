# Devpost submission — copy to paste

Everything below is written to be pasted straight into the form. Nothing here
claims anything the deployed system does not do.

---

## Project name

**VitaHome**

## Tagline (one line)

The hospital saves your life, then hands you a piece of paper. We take it from there.

## Track

**The Fortified Enterprise Fleet** — agent registry, async runtime, persistent
memory, security and governance, compliance-aware data handling.

Also entering **Startup Excellence** (Vitamedas Inc.).

---

## Elevator pitch (~200 words)

Photograph a discharge summary. In about three seconds VitaHome returns every
instruction on the page, re-ordered by what happens if you miss it — because on
the paper the fatal line is seventh, in the same font as "no lifting over ten
pounds".

Then seven agents carry it out. Appointments booked into a real FHIR store,
medications reconciled against the clinical record, a dose schedule with actual
clock times, monitoring armed against the red flags printed on *that* document,
one check-in question a day chosen from what the fleet does not yet know.

Nobody types anything. There is no chat window — a chatbot that gives advice
hands the work back to the person who was already overwhelmed.

And every agent on the bus can refuse. When the discharge summary says both
"STOP amlodipine" and "resume home medications", VitaHome does not pick the
likelier reading. It assembles both, states why it cannot choose, and puts a
licensed human in front of the decision.

In a regulated domain the interesting question is not how much a fleet does
alone. It is how precisely it knows where its authority ends.

---

## The problem

Roughly a fifth of Medicare patients are readmitted within thirty days, and a
large share of that is avoidable. Most post-discharge follow-ups are never
booked. Almost none of this is a medical failure — the medicine was right.
**Nobody executed it.**

The execution falls to whoever is standing in the corridor: usually an adult
child with a full-time job, a phone tree, and a piece of paper they have now
read three times without finding the line that matters.

---

## What it does

| | Agent | What it does |
|---|---|---|
| Pa | Parser | Document → structured plan, re-ranked by consequence, with a plain-language sentence under anything fatal |
| Rc | Reconciler | Compares the discharge list against the FHIR record; finds contradictions and refuses to resolve them |
| Sc | Scheduler | Books every follow-up into the Cloud Healthcare API — and onto a real phone, via a Google Calendar the fleet owns |
| Ph | Pharmacist | Turns "twice daily for 12 months" into a real clock; refuses anything it would have to guess at |
| Wa | Watchman | Monitors against the red flags on *this* document, not a generic alarm |
| Co | Coach | One question a day, chosen from what is genuinely unknown — and sends nothing when there is nothing to learn |
| Es | Escalator | The only path to a clinical decision, and the only agent allowed to decide a human is *not* needed |

---

## The three things worth looking at

**1 — The Failure Drill. Kill any agent, whenever you like.**

`/console/drill` terminates a real worker process: `os._exit(1)`, mid-step, no
cleanup, no graceful shutdown, message left unacked. Nothing catches it.

Recovery is infrastructure, not choreography. Pub/Sub redelivers, Cloud Run
supplies a fresh container — the worker ID in the audit trail visibly changes —
and the ledger skips every step that already completed. One FHIR appointment and
one calendar event on a real phone. Never two of either.

Every step carries a deterministic idempotency key, and that key is written
*into* the external system as the FHIR resource identifier with
search-before-create, so even a crash between "appointment booked" and "we wrote
down that we booked it" cannot double-book. At-least-once delivery plus
idempotent steps gives effectively-once execution. There is no exactly-once and
we do not claim there is.

The gap the dead worker leaves is never cleaned out of the audit trail. In a
regulated domain the scar is the evidence.

**2 — The Refusal, and the fact that it travels.**

The hero document contains a contradiction that exists in neither line alone: a
blanket "resume home medications as previously prescribed" sitting alongside a
specific "STOP amlodipine". That pairing is one of the most common real defects
in discharge paperwork.

The Reconciler applies the four changes nobody disputes and stops at amlodipine,
handing over both readings with the line each came from.

Then the refusal spreads, without anyone wiring it to:

- the **Pharmacist** builds the daily schedule and *holds* amlodipine — held,
  not dropped — because putting a disputed drug on the family's fridge at 08:00
  would be a clinical decision made silently by the agent least qualified to
  make it
- the **Coach** independently asks *"what was your most recent blood pressure
  reading?"*, giving as its stated reason that the reading is the objective data
  a clinician needs to resolve the amlodipine question

One agent refused it, one honoured the refusal, one went looking for the fact
that would settle it.

**3 — Restraint, and why it is safe.**

The Escalator can decline to page a clinician, and records the reason, the
strongest argument against its own decision, and the specific fact that would
have flipped it. A monitor that escalates everything is ignored inside a week,
and an ignored monitor is worse than none — it replaces a gap in coverage with
the belief that somebody is watching.

That is only shippable because of an asymmetry: **the model advises, the code
decides, and the code may overrule the model in exactly one direction.** If it
recommends standing down on a symptom printed on the patient's own
return-to-emergency list, the task escalates anyway and the disagreement is
written to the audit trail. There is no path where a model's reassurance
suppresses a documented red flag.

---

## How we built it

**Google Cloud Run · Pub/Sub · Firestore · Cloud Healthcare API (FHIR R4) ·
Cloud Scheduler · Secret Manager · Cloud Build · Gemini 3.5 Flash-Lite and 3.7
Flash · Agent Development Kit · A2A agent cards.**

Agents communicate through Pub/Sub messages and Firestore task documents, never
direct function calls. One topic, one push subscription per agent, separated by
an attribute filter — `dispatch` publishes with `agent="scheduler"` and has no
idea what a scheduler is or where it runs.

That claim is demonstrated, not asserted: **the Scheduler runs on its own Cloud
Run service.** Extracting it was a push-endpoint change and zero code changes,
the registry shows per-agent placement, and the Failure Drill now kills a worker
on one service while the console keeps serving from another.

Model tiers were chosen from measurements on this project's own prompts rather
than a datasheet: Flash-Lite for structured extraction on the hot path,
Flash for the two places the model exercises judgement, where the extra ~1.3s
buys something.

PHI never rides the queue. Messages carry a patient reference and a task id;
each agent fetches what it needs inside its own IAM scope.

`./infra/setup.sh <PROJECT_ID>` provisions everything from zero and is
re-runnable.

---

## Challenges we ran into

Every one of these was found by running the thing, not by reading it.

- **A poison-message loop.** A deterministically-failing task retried forever and
  saturated the service — observed at attempt 60. Now dead-lettered to the human
  queue after five attempts. Retries recover from crashes; they are not allowed
  to hide bugs.
- **Hand-timed kills were a bad instrument.** On Cloud Run the kill request often
  lands on an instance that is not the one doing the work, so the task completes
  untouched. Twice on camera would have been fatal. The trigger moved inside the
  worker: arm an agent and it kills itself from within its next step.
  Deterministic, and no less violent.
- **The worker ID was `localhost-1` on every instance.** Cloud Run gives every
  container that hostname and PID 1, so the audit log showed the *same* worker
  before and after a kill — quietly undermining the exact thing the drill proves.
- **A redelivery after completion counted one booking as two** on the Autonomy
  Ledger, and separately, `claim()` resurrected finished tasks: a redelivery of
  *successful* work walked its own attempt counter past the poison ceiling and
  dead-lettered itself. Ten fleets ended a 200-task burst in the clinician queue
  marked "failed 6 times" with all their steps completed. An exception queue that
  fills with successful work is worse than no queue.
- **The event loop was blocked.** The console went dark for 165 seconds during a
  200-task burst — not slow, never scheduled. The agent endpoint was `async def`
  but called fully blocking work directly. Moved to the threadpool; console
  latency through an identical storm is now flat at ~1.2s.
- **A credential race.** Seeding 200 patients across 16 threads gave 189
  successes and 11 bare 401s: several threads refreshing one shared credential
  at once. Locked; re-seed is 200/200 in six seconds.
- **A refusal that did not travel.** The Pharmacist was scheduling the very drug
  the Reconciler had refused to decide about.

---

## What we learned

The most valuable thing we built is not a capability, it is a boundary. Every
interesting bug on that list came from the same place: an agent doing something
reasonable in isolation that was wrong in context.

The fix was never a better prompt. It was always making the code — not the model
— hold the line.

---

## What's next

Gemini TTS so the Coach asks out loud rather than in text. Gemma 4 as a PHI
redaction sidecar before logs reach Cloud Logging. Veo for personalised
instruction clips. Cloud Trace across the fan-out.

---

## Try it

| | |
|---|---|
| Live app | https://vitahome.vitamedas.com |
| Scheduler (its own service) | https://vitahome-scheduler-205100594497.us-central1.run.app/health |
| Kill an agent yourself | https://vitahome.vitamedas.com/console/drill |
| 200 fleets | https://vitahome.vitamedas.com/console/fleets |
| Architecture | https://vitahome.vitamedas.com/architecture |
| Agent registry (A2A cards) | https://vitahome-gateway-205100594497.us-central1.run.app/registry |
| Substrate health | https://vitahome-gateway-205100594497.us-central1.run.app/health/deep |
| Source | https://github.com/bayraktartahsin/vitahome |

```bash
./scripts/preflight.sh    # everything that must be green
./scripts/drill.sh        # arm an agent, kill it mid-step, watch it recover
./scripts/monitor.sh both # the escalation, then the decision NOT to escalate
```

---

## Built by

**Tahsin Bayraktar** — Vitamedas Inc.

Vitamedas Inc. builds **Vita**, a live health product. VitaHome is the aftercare
arm of that family: the same conviction that the hard part of health is not
knowing what to do, it is executing it on a normal Tuesday when you are tired
and frightened.

---

## What is simulated, stated plainly

- the **provider directory** the Scheduler books against (labelled "provider
  directory (demo)" in every response) — the booking itself is real twice over:
  a FHIR Appointment and a Google Calendar event on a real phone
- the **home-monitoring feed** — there is no wearable; the reports are written
  as a family member would actually send them and every response is tagged
  `simulated home monitor`
- all patients are **synthetic**. There is no real patient data anywhere in this
  project.

Everything else touches a real Google Cloud service. FHIR Patients,
Appointments, MedicationRequests, MedicationDispenses and Observations are
genuine writes to a managed Cloud Healthcare API store.
