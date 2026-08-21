# Social posts

Pick one per platform. Each stands alone — don't post two variants of the same
idea to the same audience.

Post the **thread** on X and the **LinkedIn** one on LinkedIn. The short
alternates are there if the main one doesn't feel right on the day.

---

## X / Twitter — thread (recommended)

**1/**
My family got handed a discharge summary while I was in another country.

12 instructions. One of them was "do not stop ticagrelor without speaking to
cardiology."

It was seventh on the page, in the same font as "no lifting over 10 lbs."

I read it three times before I found it.

**2/**
The medicine was right. Somebody wrote it down correctly.

Then execution — book the follow-up, reconcile the meds, notice the warning
signs — became the job of whoever was standing in the corridor.

So I built seven agents to carry the page out.

**3/**
Photograph the summary → every instruction comes back re-ranked by what happens
if you miss it.

Not by where it was printed. By consequence.

~3 seconds.

**4/**
The part I didn't expect to matter most: every agent on the bus can refuse.

The document says "STOP amlodipine." Three lines later it says "resume home
medications as previously prescribed."

Amlodipine is a home medication.

**5/**
Both sentences are on the page. Neither is a typo. That pairing is one of the
most common defects in real discharge paperwork.

The Reconciler applies the 4 changes nobody disputes, then stops. It doesn't
pick the likelier reading. It hands a clinician both, with the line each came
from.

**6/**
Then something I didn't build:

→ Reconciler refuses: stop amlodipine or resume it?
→ Pharmacist schedules 4 drugs, HOLDS the fifth
→ Coach asks "what was your most recent blood pressure reading?" — because
that's the data a clinician needs to settle it

Nobody wired that.

**7/**
There's a panel that kills a worker mid-task. Real os._exit(1), no cleanup.

Pub/Sub redelivers, Cloud Run gives a fresh container, the ledger skips the
steps that already ran.

One appointment. Not two.

At-least-once + idempotent steps = effectively-once. There's no exactly-once and
I won't claim there is.

**8/**
Every interesting bug was an agent doing something reasonable in isolation that
was wrong in context.

The fix was never a better prompt. It was always making the code, not the model,
hold the line.

**9/**
My favourite: the Escalator can decide a human ISN'T needed.

First version matched textbook words — "syncope", "fainting".

"He fainted in the kitchen" contains neither.

**10/**
Worse: families rule things out constantly.

"No chest pain, no dizziness, no shortness of breath" is how someone describes
something REASSURING.

Naive matching reads that as three positive findings. It would have escalated
live on camera, in the exact demo built to show restraint.

**11/**
Everyone's optimising for how much their agents do alone.

In medicine that's the wrong axis.

The number I put on screen next to "done autonomously" is **refused**.

**12/**
Live, kill an agent yourself:
https://vitahome-web-205100594497.us-central1.run.app/console/drill

Source: https://github.com/bayraktartahsin/vitahome

Cloud Run · Pub/Sub · Firestore · Cloud Healthcare API · Gemini · Gemma
All patients synthetic.

---

## X / Twitter — single post (alternate)

The hospital saves your life, then hands you a piece of paper.

I built 7 agents that carry it out — and 4 of them can refuse.

When a discharge summary says both "STOP amlodipine" and "resume home
medications," it doesn't guess. It hands a clinician both readings.

Kill one live: [link]

---

## LinkedIn

My family was handed a discharge summary while I was in another country. Twelve
instructions on one page. One of them was "do not stop ticagrelor without
speaking to cardiology" — seventh on the sheet, in the same font as "no lifting
over ten pounds."

I read it three times before I found the line that mattered.

The medicine was right. Someone wrote it down correctly. What failed was
execution — and execution had been handed to a frightened family.

Over the last two weeks I built VitaHome: seven agents that carry the page out.
Photograph a discharge summary and it re-ranks every instruction by what happens
if it's missed, books the follow-ups into a real FHIR store, turns "twice daily
for twelve months" into an actual clock, and monitors for the warning signs
printed on that specific document.

The part I did not expect to be the most interesting: four of those agents can
refuse.

The sample document says "STOP amlodipine 5 mg." Three lines later it says
"resume home medications as previously prescribed." Amlodipine is one of his
home medications. Both sentences are on the page, neither is a typo, and that
exact pairing is one of the best-documented defects in real discharge paperwork.

The system applies the four medication changes nobody disputes — and then stops.
It doesn't pick the likelier reading. It assembles both interpretations, cites
the line each came from, and hands a clinician the decision.

What surprised me was what happened next, which I didn't design. The Pharmacist
built the daily schedule and held that one drug pending the decision. The Coach,
which asks one question a day, chose "what was your most recent blood pressure
reading?" — because that reading is the objective data a clinician needs to
resolve it. Three agents converged on one open question without being wired to.

Every hard bug I hit came from the same place: an agent doing something
reasonable in isolation that was wrong in context. The fix was never a better
prompt. It was always making the code, rather than the model, hold the line.

Most of us building agents right now are optimising for how much the system does
alone. In a regulated domain that's the wrong axis. What's worth building is a
system that knows precisely where its authority ends.

The metric I put on screen next to "done autonomously" is "refused." Deliberately.

It's live, and there's a panel that lets you kill any agent mid-task and watch
it recover. Link in the comments.

#AI #HealthTech #GoogleCloud #AgenticAI

---

## Comment to drop under the LinkedIn post

Live app — press "Use the sample discharge summary":
https://vitahome-web-205100594497.us-central1.run.app

Kill an agent yourself:
https://vitahome-web-205100594497.us-central1.run.app/console/drill

Source and the full write-up, including the four distributed-systems bugs that
only showed up under load:
https://github.com/bayraktartahsin/vitahome

---

## Notes on posting

- **Lead with the paper, never with the architecture.** The corridor is the part
  everyone has lived; Pub/Sub is not.
- **One personal line, once.** "I was in another country" does the work. Saying
  it twice turns it into a device.
- **Don't oversell the refusal.** State what it does and let the reader draw the
  conclusion. "Calibrated non-autonomy" is a phrase for a judging rubric, not
  for a post.
- **Say the patients are synthetic**, every time, unprompted.
- The bug list is the most re-shareable content here. Engineers share bugs.
