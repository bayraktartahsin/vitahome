# How to test VitaHome yourself

Two ways: click through it in a browser (5 minutes, no setup), or run the
scripts (one command, checks 38 things).

Everything below uses synthetic patients. There is no real patient data
anywhere in this project.

---

## A · Click through it — 5 minutes

**https://vitahome.vitamedas.com**

Do these in order. It takes about five minutes and covers every claim.

### 1 · The parse — 60 seconds

Go to **[/capture](https://vitahome.vitamedas.com/capture)**
and press **"Use the sample discharge summary."**

**What to look for**
- A timer counts up while it reads. It settles around **3 seconds**.
- The result says how long it took and which model did it. Compare that to the
  timer you just watched — they should agree.
- **The order.** The ticagrelor line is at the top, in red. On the document
  itself it is line 7, in the same font as "no lifting over 10 lbs".
- Under it, a sentence in plain English about what happens if it is missed. That
  sentence is not on the document.
- On the right of each row, the line number. That is checkable against the
  source.

**Try to break it:** press "Take a photo" and upload *anything* — a menu, a
receipt, a screenshot of this page. It should tell you what the document is and
return **no instructions**. It must not invent medical content from a
non-medical page. (Photographed documents show `~line 5` with a tilde: for an
image the model counts visible lines, so the number is approximate, and the UI
says so rather than pretending otherwise.)

### 2 · The refusal — 90 seconds

Go to **[/console](https://vitahome.vitamedas.com/console)**.
Press **"reset"**, then **"seed patient"**, then **"reconcile medications"**.

Wait ~20 seconds.

**What to look for**
- A purple **REFUSED** card appears. The question is about **amlodipine**.
- Read the two options. One cites instruction i_05 (*STOP amlodipine*), the
  other cites i_06 (*resume home medications*). **Both of those sentences are on
  the document.** Neither is a typo — that pairing is a real and common defect
  in discharge paperwork, and it is invisible if you read either line alone.
- The ledger tile **refused** goes to 1.

Now press **"reconcile medications"**'s neighbour, **"book every follow-up"**,
and watch the audit stream on the right fill up.

### 3 · The refusal spreading — the best 30 seconds

Still on `/console`, open a second tab at
**[/today](https://vitahome.vitamedas.com/today)**.

Back on `/console`, dispatch the Pharmacist and the Coach. The quickest way is
the terminal:

```bash
curl -X POST "https://vitahome-gateway-205100594497.us-central1.run.app/demo/dispatch" -H 'Content-Type: application/json' -d '{"patientId":"p_hero","agent":"pharmacist"}'
```

```bash
curl -X POST "https://vitahome-gateway-205100594497.us-central1.run.app/demo/dispatch" -H 'Content-Type: application/json' -d '{"patientId":"p_hero","agent":"coach"}'
```

Wait ~30 seconds, then reload `/today`.

**What to look for**
- A day laid out **by clock time**, not by drug. 08:00, 20:00, 22:00.
- Four drugs scheduled. **Amlodipine is not one of them** — it is at the bottom
  under *"waiting on the care team"*, held, with *"don't take this one until you
  hear back."* Held, not missing: a drug that quietly vanishes is how somebody
  stops taking something by accident.
- At the top, today's question — and it will usually be about something that
  would help resolve the amlodipine decision.
- Press **▶︎ listen**. It reads the question aloud.

Nobody wired those three agents together. One refused, one honoured the refusal,
one went looking for the fact that would settle it.

### 4 · Kill an agent — 90 seconds

Go to **[/console/drill](https://vitahome.vitamedas.com/console/drill)**.

Press **arm** on the Scheduler, then **"▸ Start a task"**.

Then open `/console` and watch the audit stream.

**What to look for, in order**
```
step 'resolve_provider' completed
AGENT_DOWN  killed mid-step 'fhir_appointment' — process exiting without ack
redelivery  redelivered — attempt 2
lease       leased by <a DIFFERENT worker id>
skip        step 'resolve_provider' already completed — skipped on replay
step 'fhir_appointment' completed
```

Three things worth checking yourself:
1. **The worker id changes.** That is a different process. The first one is gone.
2. **The completed step is skipped, not repeated.** That is the whole point.
3. **One appointment, not two.** The task card shows one `externalRef`.

Nothing catches that kill. It is a real `os._exit(1)` with no cleanup. Recovery
comes from Pub/Sub redelivering an unacked message and Cloud Run supplying a
fresh container — not from any code in this project.

The red gap stays in the audit trail permanently. It is not cleaned up.

### 5 · Escalate, then restraint — 90 seconds

On `/console`, press **"report: chest pain"**. Wait ~25 seconds.

- An amber **ESCALATED** card appears, marked **emergency**, with a **5-minute
  SLA clock counting up**. It carries the reason *and* the strongest argument
  against its own decision.
- Press **acknowledge · Dr. Chen**. That is the only way it closes — no agent
  can. Watch **closed by a human** go to 1.

Now the harder one. Press **"report: lightheaded"**. Wait ~25 seconds.

- **Nothing appears in the queue.** Read the audit stream: the Escalator *stood
  down* and recorded why, plus what would have changed its answer.

That is the interesting behaviour. Anything can be built to panic.

### 6 · Scale — 60 seconds

Go to **[/console/fleets](https://vitahome.vitamedas.com/console/fleets)**.

Press **"seed 200 fleets"** (~6s), then **"hand work to all 200"**.

**What to look for**
- The grid turns over as real Scheduler tasks run.
- **The page stays responsive the whole time** — ~1.2s per refresh.
- **Click any square.** There is a real patient behind it, with a real FHIR
  record. Nothing here is painted.

---

## B · Run the scripts — one command

```bash
git clone https://github.com/bayraktartahsin/vitahome && cd vitahome
```

```bash
./scripts/preflight.sh
```

Checks that every piece is *up*: both services, the FHIR store, Gemini, seven
agent cards, all six Pub/Sub subscriptions with their filters and deadlines, and
whether a chaos arm was left set from a previous rehearsal.

```bash
./scripts/fullrun.sh
```

Checks that every piece is *right*. 38 assertions across every claim above —
parse ranking and line numbers, the refusal and whether it travels, voice,
escalation with its SLA, the restraint case, human resolution and its
idempotence, **three consecutive Failure Drills**, the PHI audit including
absence of false positives, adversarial intake of a restaurant menu, and all
seven web pages. Exits non-zero if anything fails.

```bash
./scripts/fullrun.sh --storm
```

Adds the 200-fleet burst and samples console latency throughout it.

Individually:

```bash
./scripts/drill.sh
```

```bash
./scripts/monitor.sh both
```

---

## C · Poke the API directly

```bash
curl https://vitahome-gateway-205100594497.us-central1.run.app/health/deep
```

Proves the FHIR store and Gemini are both live, from the service itself.

```bash
curl https://vitahome-gateway-205100594497.us-central1.run.app/registry
```

Seven A2A agent cards. Note which one is `humanTerminated`.

```bash
curl https://vitahome-gateway-205100594497.us-central1.run.app/usage
```

Tokens used per model since the instance started. Counted, not estimated.

Hand the log auditor something it should catch:

```bash
curl -X POST "https://vitahome-gateway-205100594497.us-central1.run.app/compliance/scan" -H 'Content-Type: application/json' -d '{"lines":["agent=scheduler pid=p_hero task=t_ab12","Patient: Robert Hayes, 60M MRN 88213 with chest pain","leased by nj4-f7210a"]}'
```

It should flag the middle line and leave the other two alone. Flagging `p_hero`
or a task id would be a false positive, and a scanner that cries wolf on an
opaque identifier trains people to ignore it.

---

## D · Run the tests

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

```bash
.venv/bin/python -m pytest tests -q
```

172 tests, about a second. No network, no Google credentials needed — Firestore,
FHIR and Gemini are all faked.

---

## If something looks wrong

Reset the demo patient and start again:

```bash
curl -X POST "https://vitahome-gateway-205100594497.us-central1.run.app/demo/reset?patientId=p_hero"
```

The services scale to zero when idle, so **the first request after a quiet spell
takes about a second** while a container starts. Subsequent ones are ~0.4s. If
something feels slow, hit it twice.

If a drill seems not to fire, check nothing is still armed:

```bash
curl https://vitahome-gateway-205100594497.us-central1.run.app/chaos/status
```
