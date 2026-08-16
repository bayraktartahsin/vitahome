# VitaHome — demo script

One take. Nothing cut, nothing sped up. The rules ask for an unedited live demo,
and an unedited demo is also the strongest possible claim: everything you are
about to watch is happening on Google Cloud while I talk.

Target: **4:00**. Hard ceiling 4:30.

---

## The rule that shapes every beat

The fleet is fast. A booking lands in under two seconds; the parse is about one.
If I narrate while it runs, I am talking over the proof and the video becomes a
voiceover with a progress bar behind it.

So every beat is built the same way:

> **SET UP** — say what is about to happen, and what would make it fail.
> **WATCH** — press the button. Stop talking. Let it land.
> **PAY OFF** — say what just happened and why it was hard.

The silence in the middle is not dead air. It is the evidence. Rehearse holding
it — three seconds of quiet feels like thirty from behind the camera and like
nothing at all to the person watching.

---

## Before you hit record

- [ ] `./scripts/preflight.sh` green — every service, FHIR store, and subscription live
- [ ] Hero patient seeded, ledger reset to zero
- [ ] Phone in frame, unlocked, notifications on, volume up, Do Not Disturb **off**
- [ ] Browser: two windows side by side — family view left, clinician console right
- [ ] Zoom to 125%. Judges watch on laptops.
- [ ] The paper discharge summary physically in your hand
- [ ] Close Slack, mail, everything with a badge
- [ ] One rehearsal of the Failure Drill, then reset. Never demo a drill you have not run that day.

---

## 0:00 — The ten-second challenge

**SET UP** *(hold the paper up to camera)*

> This is a discharge summary. A dozen instructions on it. At least one of them
> kills him if it gets missed.
>
> Find it. You have ten seconds.

*(Say "a dozen", not a specific number. The parse is live and the model splits
borderline lines differently between runs — it has come back with twelve and
with thirteen. Naming an exact count on camera invites a mismatch with the
screen thirty seconds later, over something that does not matter.)*

*(Hold the paper still. Say nothing. Count ten in your head — actually count,
do not guess. This silence is the whole opening.)*

**PAY OFF**

> It took me three readings.
>
> If you have ever stood in a hospital corridor holding your parent's paperwork,
> you already know this feeling. I was in another country when my family got
> this one.

*(Say that once. Flat. Do not add to it, do not repeat it later. The paper comes
back at the end as a prop, the sentence does not.)*

---

## 0:30 — The photograph

**SET UP**

> So I photograph it.
>
> No typing, no forms, no chat window. The document is the interface.

**WATCH** *(take the photo, upload, stop talking)*

*(About three seconds. The page deconstructs into individual instructions,
re-sorted by what happens if you miss them. The ticagrelor line lands at the
top, in red, with a plain-language sentence under it.)*

**PAY OFF**

> Three seconds.

*(Read the timer off the screen — the UI prints the measured latency and the
model name, so say whatever it actually shows. Measured on this document:
2.8-3.3 seconds warm, on gemini-3.5-flash-lite. Do not say "one second"; the
one-second figure was a shorter test prompt and it is not what this does.)*

> Top of the list, in red — do not stop ticagrelor. That is the one. Stopping a
> blood thinner early after a stent is how people die in the month after they
> get sent home feeling fine.
>
> It is first not because it appears first. On the paper it is seventh, in the
> same font as "no lifting over ten pounds". It is first here because it is
> fatal. The fleet re-ranks the page by consequence.
>
> And that sentence underneath it is not on the document. That is the fleet
> explaining, to a frightened family member at midnight, what actually happens
> if they get it wrong.

---

## 1:00 — Execution, counted out loud

**SET UP**

> Now the part nobody does. Somebody has to actually carry those instructions
> out — book the cardiology follow-up, reconcile what he takes against what he
> was taking, route the prescriptions, arm monitoring for the specific warning
> signs on this specific document.
>
> That is usually a daughter with a full-time job and a phone tree.
>
> Watch the counter, and watch my phone.

**WATCH** *(press Execute. Silence. Let it run — roughly 20 seconds.)*

*(Tasks appear. Bookings land. The phone buzzes on camera with a real calendar
invite. The Autonomy Ledger climbs.)*

**PAY OFF**

> Three appointments booked into a real FHIR store. A real calendar invite —
> that is my actual phone, that buzz was not a sound effect. Prescriptions
> routed. Monitoring armed.
>
> Nobody typed anything. There is no chat window in this product. That is
> deliberate — a chatbot that gives you advice hands the work back to you. This
> does the work.

---

## 1:30 — The Refusal

**SET UP**

> And then it stops.
>
> One instruction on this sheet is genuinely ambiguous — you can read it two
> ways, and the two readings imply different drugs. Watch what it does with it.

**WATCH** *(the Reconciler flips to refused. Silence.)*

**PAY OFF**

> It refused.
>
> It did not guess, it did not average the two readings, it did not pick the
> likelier one. It assembled both interpretations, stated why it could not
> choose, and put a licensed human in front of the decision.
>
> That is the counter on the right — **refused: 1**. I put that number on screen
> next to the autonomous count on purpose.
>
> Everyone in this competition is optimising for how much their agents do alone.
> In medicine that is the wrong axis. The thing worth building is a system that
> knows precisely where its authority ends. The fleet executes the mechanical.
> Only a clinician decides the clinical.

---

## 2:00 — The Failure Drill *(hand over the knife)*

**SET UP**

> Everything so far assumed the happy path. Let me break it.
>
> This panel kills a worker process — a real `os._exit`, no cleanup, no graceful
> shutdown, no chance to finish what it was doing. Pick an agent. Any of them.
>
> *(If a judge is live: let them choose and click. If not: "I'll take the
> Scheduler, mid-booking — the worst possible moment, because a retry there is
> how you double-book a patient.")*

**WATCH** *(arm, dispatch, stop talking — about 30 seconds)*

*(The worker dies mid-step. The audit stream shows a red gap where the
heartbeat stopped. Then: redelivery. A different worker ID. Completed steps
marked SKIPPED. Only the remaining work runs. Task completes.)*

**PAY OFF**

> The process is gone. Nothing caught that — it was not an exception handler,
> there was no try/finally, the container did not shut down cleanly.
>
> What recovered it was infrastructure. The Pub/Sub message was never acked, so
> Pub/Sub redelivered it. Cloud Run had a fresh container. Look at the worker
> ID — different process.
>
> And then the important part: the steps it had already finished are marked
> skipped, not repeated. Every side effect carries a deterministic idempotency
> key, and the key is written into the external system too — so even a crash in
> the gap between "appointment booked" and "we wrote down that we booked it"
> cannot double-book.
>
> At-least-once delivery plus idempotent steps gives you effectively-once
> execution. There is no exactly-once, and I am not going to claim there is.
>
> One appointment. Not two.
>
> The red gap stays in the audit trail permanently. I do not clean it up. In a
> regulated domain the scar is the evidence.

---

## 2:45 — The live event, and the restraint

**SET UP**

> This next part I do not control the timing of. Monitoring has been armed since
> minute one, watching for the red flags written on *this* document.

**WATCH** *(vitals cross the threshold. Watchman fires. Escalator decides. The
console lights up.)*

**PAY OFF**

> Escalated to a human. Note it did not treat, did not advise, did not reassure
> — it paged a clinician and started an SLA clock.

**SET UP** *(the counter-beat — this is the beat that separates the demo from
every other submission)*

> Now the harder case.

**WATCH** *(a second event fires. The Escalator declines to escalate.)*

**PAY OFF**

> Same monitor, different reading, and it decided a human was *not* needed.
>
> Anything can be built to panic. Restraint is the expensive part — a system
> that escalates everything gets ignored inside a week, and then it is worse
> than nothing.

---

## 3:20 — Scale, and generality

**SET UP**

> One patient is a demo. Here is the clinician console.

**WATCH** *(200 fleets. Exception queue. SLA timers.)*

**PAY OFF**

> Two hundred concurrent patient fleets, one clinician. Sorted by what needs a
> human, not by what arrived last.
>
> And nothing in here is cardiac.

**WATCH** *(photograph a pediatric vaccine schedule — 15 seconds)*

**PAY OFF**

> Same fleet. Same seven agents. Different document. Wherever a human being is
> handed a piece of paper and expected to execute it correctly for six weeks,
> this works.

---

## 3:45 — Back to the paper

*(Pick up the discharge summary. Hold it up. Same framing as 0:00.)*

> The hospital saves your life.
>
> Then it hands you a piece of paper.
>
> We take it from there.

*(Stop talking. Let it sit. End the recording on silence, not on a thank-you.)*

---

## Delivery notes

**Pace.** Slower than feels right. Nerves push you 20% faster than your
rehearsal, and the demo does not need you to hurry — the software is the thing
that is fast.

**Volume.** Drop, do not raise, on the two emotional lines (0:00 payoff, 3:45).
Quiet reads as certainty. Loud reads as a pitch.

**Do not apologise.** Not for the sandbox, not for synthetic data, not for the
one simulated endpoint. Declare it once, plainly, with the badge on screen, and
move on. Judges forgive declared simulation and never forgive discovered
simulation.

**If something breaks.** Do not restart and do not edit. Say what broke, say
what the system did about it, and continue. A fleet that survives an unplanned
failure on camera is worth more than a clean run — but only if you stay calm,
so decide now that this is fine.

**The two sentences to land above all others**, in priority order:

1. *"It refused."*
2. *"One appointment. Not two."*

If everything else gets rushed, those two land clean.
