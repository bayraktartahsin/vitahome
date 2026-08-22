# I built an agent fleet that refuses to do things

*Tahsin Bayraktar · Vitamedas Inc.*

---

My family was handed a discharge summary while I was in another country. Twelve
instructions on one sheet of paper. One of them was *do not stop ticagrelor
without speaking to cardiology*, and it was seventh, printed in the same font as
*no lifting over ten pounds*.

I read that page three times before I found the line that mattered.

That is the whole problem, and it is not a medical one. The medicine was
correct. Somebody wrote it down correctly. Then it was handed to a frightened
family and the execution — book the cardiology follow-up, reconcile what he
takes against what he was taking, notice the warning signs — became the
responsibility of whoever happened to be standing in the corridor.

So I spent two weeks building VitaHome: seven agents that carry the page out.
Photograph a discharge summary, and it re-ranks every instruction by what
happens if you miss it, books the appointments into a real FHIR store, turns
"twice daily for twelve months" into an actual clock, and watches for the red
flags printed on *that* document.

The part I did not expect to be the interesting part is that four of those
agents can refuse.

---

## The line that is in neither line

The hero document contains a contradiction. It says **STOP amlodipine 5 mg —
replaced by metoprolol**. It also says, three lines later, **resume home
medications as previously prescribed**. Amlodipine is one of his home
medications.

Both sentences are on the page. Neither is a typo. That exact pairing —
boilerplate "resume home meds" text sitting alongside a specific stop order — is
one of the most common defects in real discharge paperwork, and it is not
detectable by reading either line on its own.

The Reconciler finds it, applies the four medication changes nobody disputes,
and then stops. It does not pick the likelier reading. It assembles both
interpretations with the line each came from, and hands a clinician the choice.

Then something happened that I did not build.

The Pharmacist, which reads active medications out of the clinical record, found
amlodipine still sitting there — because of course it is, nobody has decided —
and put it on the family's daily schedule at 08:00. Which is a clinical
decision, made silently, by the agent least qualified to make it.

I fixed that: refusals propagate now. But the fix produced something better than
the fix. Watch what the three agents do with one open question:

- the **Reconciler** refuses: stop amlodipine, or resume it?
- the **Pharmacist** schedules four drugs and *holds* the fifth, pending that decision
- the **Coach**, which gets one check-in question a day and picks it from what
  the fleet does not yet know, asks: *"What was your most recent blood pressure
  reading?"* — giving as its reason that the reading is the objective data a
  clinician needs to resolve the amlodipine question

Nobody wired that. One agent refused, one honoured the refusal, and one went
looking for the fact that would settle it.

---

## The model advises. The code decides.

Every interesting bug I hit came from the same place: an agent doing something
perfectly reasonable in isolation that was wrong in context. And the fix was
never a better prompt.

The clearest case is the Escalator, which decides whether to wake a clinician.
It is allowed to say no. That is deliberate — a monitor that escalates
everything is ignored inside a week, and an ignored monitor is worse than none,
because it replaces a gap in coverage with the belief that somebody is watching.

Restraint is only shippable because of an asymmetry. The model recommends; the
code decides; and the code may overrule the model in exactly one direction.
Recommend standing down on a symptom printed on the patient's own
return-to-emergency list, and it escalates anyway and writes the disagreement to
the audit trail. There is no path in that file where a model's reassurance
suppresses a documented red flag.

I wrote the first version of that check with textbook vocabulary — "syncope",
"fainting". Then I tested it against how a daughter actually writes at midnight
and found "he fainted in the kitchen" contains none of those words.

Worse: family reports rule things out constantly. *"No chest pain, no dizziness,
no shortness of breath"* is how a careful person describes something
reassuring — and naive keyword matching reads it as three positive findings. My
restraint scenario says exactly that. It would have escalated live, on camera,
and destroyed the segment it was built to demonstrate.

There is now a small negation matcher that stops at clause boundaries, so *"no
dizziness, but he does have chest pain"* negates the first and not the second.
Both demo scenarios are pinned by name in the test suite.

---

## Then I killed it, repeatedly

The demo has a panel that terminates a worker process. Real `os._exit(1)`,
mid-step, no cleanup, no graceful shutdown. Nothing catches it.

The task survives because of infrastructure, not choreography. The Pub/Sub
message was never acked, so it comes back. Cloud Run supplies a fresh
container — the worker ID in the audit trail visibly changes — and the ledger
skips every step that already completed.

```
lease       leased by nj4·f7210a
AGENT_DOWN  killed mid-step 'resolve_provider' — process exiting without ack
redelivery  redelivered — attempt 2 (previous worker did not finish)
lease       leased by nj4·450f78          ← different process
skip        step 'resolve_provider' already completed — skipped on replay
```

One appointment. Not two.

At-least-once delivery plus idempotent steps gives you effectively-once
execution. There is no exactly-once, and I am not going to claim there is.

Building that found four bugs I would not have found by reading the code.

**The worker ID was `localhost-1` on every instance.** Cloud Run gives every
container that hostname and PID 1. So the audit log showed the *same* worker
before and after the kill — quietly undermining the exact thing the drill exists
to prove.

**The event loop was blocked.** During a 200-task burst the console went dark
for 165 seconds. It was not slow; it was never scheduled. The agent endpoint was
`async def` and called fully-blocking work directly, so every task held the loop
for its entire duration and the instance served nothing else.

**Finished tasks were dead-lettering themselves.** `claim()` set a task back to
"leased" and bumped its attempt counter unconditionally — so a redelivery of
*successful* work walked its own counter past the poison ceiling and escalated.
Ten fleets ended that burst in the clinician's queue marked "failed 6 times",
with all three of their steps sitting there completed. An exception queue that
fills up with successful work is worse than no queue: it teaches the clinician
to stop reading it, which is precisely the failure the Escalator's restraint
exists to prevent.

**A credential race.** Seeding 200 patients across 16 threads gave 189 successes
and 11 bare 401s — several threads refreshing one shared credential at once.

None of those are model problems. All of them are the ordinary distributed
systems tax, and every one was found by running the thing rather than reading it.

---

## What it costs

An idle deployment was billing about $23 a month, entirely because two Cloud Run
services were pinned to one always-on instance each. The reason was cold
starts — around eight seconds, long enough to notice.

Startup CPU boost gives the container full CPU while it boots instead of the
throttled share an idle instance normally gets. It costs nothing extra. After
that:

```
gateway   cold 0.73s
web       cold 0.80s
```

Both services scale to zero now and the app costs approximately nothing to leave
running.

For contrast, here is a complete demo run — parse, reconcile, schedule doses,
monitor, escalate, check in — measured end to end:

```
gemini-3.5-flash-lite   2 calls   1,855 in   1,763 out
gemini-3.7-flash        4 calls   1,953 in     919 out
────────────────────────────────────────────────────
total                   6 calls   3,808 in   2,682 out
```

Six thousand tokens for the entire thing. The models were never the expense.

---

## The argument

Everyone building agents right now is optimising for how much the system does on
its own. In medicine that is the wrong axis.

The thing worth building is a system that knows precisely where its authority
ends — that executes the mechanical and hands every clinical judgement to a
licensed human, with the options already assembled so the human is deciding
rather than researching.

The number I put on screen next to "done autonomously" is **refused**. On
purpose.

VitaHome never diagnoses and never prescribes. It executes instructions a
clinician already wrote. Every instruction carries the line number it came from,
so anything it did can be checked against the paper in your hand.

---

**Try it:** [vitahome-web-205100594497.us-central1.run.app](https://vitahome-web-205100594497.us-central1.run.app)
— press "Use the sample discharge summary". The chaos panel is at `/console/drill`;
kill whichever agent you like.

**Source:** [github.com/bayraktartahsin/vitahome](https://github.com/bayraktartahsin/vitahome)

Built on Cloud Run, Pub/Sub, Firestore, the Cloud Healthcare API, Gemini and
Gemma. All patients are synthetic.
