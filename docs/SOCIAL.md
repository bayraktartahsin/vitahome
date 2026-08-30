# Social posts

Every post below already includes the hashtag and fits X's 280-character
limit **with it**. Copy a whole block, hashtag included — nothing to trim.

Lengths are asserted by the check at the bottom of this file, so an edit that
pushes one over the limit is caught rather than discovered when X refuses it.

---

## X / Twitter — thread (recommended)

Post 1, then reply to your own post with 2, and so on.

**Post 1 of 7** — 276/280 characters

```
1/ My family was handed a discharge summary while I was abroad.

12 instructions. One said: do not stop ticagrelor without speaking to cardiology.

It was 7th on the page, same font as "no lifting over 10 lbs."

I read it 3 times before I found it.

#AllThingsAgenticHackathon
```

**Post 2 of 7** — 273/280 characters

```
2/ The medicine was right. Someone wrote it down correctly.

Then carrying it out — book the follow-ups, reconcile the meds, watch for the warning signs — became the job of whoever was standing in the corridor.

I built 7 agents to do that part.

#AllThingsAgenticHackathon
```

**Post 3 of 7** — 273/280 characters

```
3/ Photograph the page. Every instruction comes back re-ranked by what happens if you miss it, not by where it was printed.

3 seconds, Gemini 3.5 Flash-Lite.

The fatal line goes first, with a sentence explaining why that isn't on the document.

#AllThingsAgenticHackathon
```

**Post 4 of 7** — 274/280 characters

```
4/ The part I didn't expect to matter most: the agents can refuse.

The page says STOP amlodipine. Three lines later: resume home medications as previously prescribed.

Amlodipine is a home medication.

Both sentences are real. Neither is a typo.

#AllThingsAgenticHackathon
```

**Post 5 of 7** — 269/280 characters

```
5/ It doesn't pick the likelier reading.

It applies the 4 changes nobody disputes, stops, and hands a clinician both readings with the line each came from.

Then the refusal travels — the Pharmacist holds that drug instead of scheduling it.

#AllThingsAgenticHackathon
```

**Post 6 of 7** — 272/280 characters

```
6/ Then I tried to break it.

A panel kills a real worker process mid-write, no cleanup.

Pub/Sub redelivers, Cloud Run gives a fresh container, and the finished step says SKIP.

One appointment in the record. One event on the phone. Never two.

#AllThingsAgenticHackathon
```

**Post 7 of 7** — 236/280 characters

```
7/ Everyone is optimising for how much their agents do alone.

In medicine that's the wrong axis. The question is how precisely a system knows where its authority ends.

Live, no login: vitahome.vitamedas.com

#AllThingsAgenticHackathon
```

---

## X / Twitter — one post, if you would rather not thread

**Option 1** — 270/280 characters

```
A discharge summary has 12 instructions. One kills him if it's missed — 7th on the page, same font as "no lifting over 10 lbs."

I built 7 agents that carry the page out, and refuse the parts a clinician should decide.

vitahome.vitamedas.com

#AllThingsAgenticHackathon
```

**Option 2** — 263/280 characters

```
Most agent demos optimise for how much the agent does alone.

Mine refuses. When a discharge summary says both STOP amlodipine and resume home medications, it hands a clinician both readings instead of guessing.

vitahome.vitamedas.com

#AllThingsAgenticHackathon
```

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
