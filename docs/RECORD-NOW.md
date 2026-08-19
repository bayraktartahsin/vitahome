# RECORD-NOW — the only file you need

Follow this top to bottom. Every command is copy-paste. Every click is named.
Every word you speak is written out in Part D.

---

# PART A — One-time setup (do once, ~15 minutes)

## A1 · Put the fleet's calendar on your phone

The calendar is shared with **tahsin@gravitilabs.com**.

1. On your **phone**, open the **Gmail** app, account **tahsin@gravitilabs.com**.
2. Find the email from *Google Calendar* (subject contains **"VitaHome — appointments (demo)"**).
3. Tap **"Add this calendar"**. Done.

**If there is no email**, open this exact link on your phone (logged in as
tahsin@gravitilabs.com) and tap **Add**:

https://calendar.google.com/calendar/u/0/r?cid=NzEyNDFkMDAxMjNkOGE1MDE2OTkzZWVkNmQzODIyMTViN2Q1NDc4ZDJjMTQ0YjExYjJkMWViN2ZiNDJmODZiZEBncm91cC5jYWxlbmRhci5nb29nbGUuY29t

**If the calendar still doesn't show events later:** Google Calendar app →
tap your **profile picture** (top right) → **Settings** → under
*tahsin@gravitilabs.com* tap **VitaHome — appointments (demo)** → turn **Sync** ON.

## A2 · Test the calendar (2 minutes)

1. On your Mac, open Chrome and go to: https://vitahome.vitamedas.com/console
2. Click the button **`seed patient`**. Wait until the small text under the
   buttons says *"seeding the patient — done"*.
3. Click **`book follow-ups`**. Wait 20 seconds.
4. On your phone: open **Google Calendar**, swipe down to refresh, and look at
   **next week** (around Tuesday/Thursday 10:00). You should see appointments
   like *"Cardiology — Dr. Chen"*.
5. Seen them? Calendar is done forever. Not seen? Do the Sync-ON step in A1.

## A3 · Print the paper prop

1. Press **Cmd+Space**, type `Terminal`, press **Enter**.
2. Paste this and press Enter (it opens the document):

```bash
open -a TextEdit "/Users/bayraktar/Documents/New Apps/Hackhaton/vitahome/docs/discharge-summary.txt"
```

3. In TextEdit press **Cmd+P**, then click **Print**. Keep the page on your desk.

## A4 · Set up QuickTime (your recorder)

1. Press **Cmd+Space**, type `QuickTime Player`, press **Enter**.
   (If a file dialog opens, press **Esc**.)
2. Menu bar → **File → New Screen Recording**.
3. In the bar that appears, click **Options** → under **Microphone** select
   **MacBook Pro Microphone** (or your headset).
4. Don't record yet — just confirm you know where this is.

**Optional but great — show your phone inside the recording:**
1. Connect your iPhone to the Mac with a **cable**.
2. QuickTime menu bar → **File → New Movie Recording**.
3. Next to the red record button, click the small **▾ arrow** → under
   **Camera**, choose your **iPhone**.
4. A window with your phone's screen appears. Drag it to the **bottom-right
   corner** and make it small. Leave it there — it will be part of the recording.
   (On the phone itself, open the Google Calendar app.)

---

# PART B — Before every take (~5 minutes)

## B1 · Health check

Open Terminal (**Cmd+Space** → `Terminal` → **Enter**), paste this **whole block**, press Enter:

```bash
cd "/Users/bayraktar/Documents/New Apps/Hackhaton/vitahome" && ./scripts/preflight.sh
```

Wait ~1 minute. The last line must say **"clear to record"** in green.
If anything is red, paste the red line to Claude.

## B2 · Arrange your two browser windows

1. **Window A — THE ONE YOU RECORD.** Open a Chrome window at:
   `https://vitahome.vitamedas.com/capture`
   Press **Cmd and +** twice (zoom to 125%). Make this window large, centered.
2. **Window B — the teleprompter (NOT recorded).** Open a **separate** Chrome
   window (**Cmd+N**) at:
   `https://vitahome.vitamedas.com/director`
   Put it on your **second screen**. No second screen? Make Window A fill the
   **left ⅔** of the screen and Window B the **right ⅓** — you'll record only
   Window A (QuickTime lets you drag-select just that area).

## B3 · Reset the demo

On Window B (the Director page):
1. Click **`1 · reset the demo patient`** — wait for green "done".
2. Click **`2 · seed the patient`** — wait for green "done".

## B4 · Silence everything

1. Mac: click the **clock** (top-right corner) → turn **Focus / Do Not Disturb ON**.
2. Phone: Do Not Disturb ON (Google Calendar still works).
3. Quit Slack, WhatsApp, Mail — anything that pops up.
4. Phone on the desk, Google Calendar app open, screen unlocked.
5. Printed paper in your hand.

---

# PART C — The take

1. QuickTime → **File → New Screen Recording** → drag to select **Window A's
   area** (or choose the screen that has Window A) → click **Record**.
2. On Window B click **Start →**.
3. From now on: do what the big text says. Press the **→ (right-arrow) key**
   after each cue.
   - **SAY** (white) = read it aloud
   - **DO** (amber) = one click / pick up the phone
   - **SILENCE** (green) = say NOTHING and wait
4. At the last cue: stop the recording (click the **⏺ stop icon** in the Mac
   menu bar, top-right).

**If something breaks mid-take:** say *"and this is live, so let's watch it
recover"* — and keep going. Do not restart.

---

# PART D — Every word and every click, in order

This is the same content the Director shows you — printed here so you can
rehearse from paper. **Bold** = say it aloud. `CLICK` = do it. *(wait)* = shut up
and let the screen work.

**Scene 1 — the paper** *(Window A is on /capture)*

1. **"This is a discharge summary. A dozen instructions on it. At least one of them kills him if it gets missed."**
2. **"Find it. You have ten seconds."**
3. *(hold the paper up — count to 10 silently)*
4. **"It took me three readings."**
5. **"If you have ever stood in a hospital corridor holding your parent's paperwork, you know this feeling. I was in another country when my family got this one."** *(flat voice, once, never again)*

**Scene 2 — the photograph**

6. **"So I photograph it. No typing, no forms, no chat window. The document is the interface."**
7. `CLICK` the white button **"Use the sample discharge summary"** — then silence until the list finishes.
8. **"___ seconds."** *(read the number the screen shows, top right)*
9. **"Top of the list, in red — do not stop ticagrelor. That is the one. Stopping a blood thinner early after a stent is how people die in the month after they go home feeling fine."**
10. **"On the paper it is seventh, in the same font as 'no lifting over ten pounds'. It is first here because it is fatal. The fleet re-ranks the page by consequence."**
11. **"And the sentence underneath it is not on the document. That is the fleet explaining to a frightened family member what actually happens."**

**Scene 3 — execution** *(switch Window A to /console — type it in the address bar or use the top-bar link)*

12. **"Now the part nobody does. Somebody has to carry those instructions out. That is usually a daughter with a full-time job and a phone tree."**
13. **"Watch the counters — and watch my phone."**
14. `CLICK` **"book follow-ups"**, then `CLICK` **"reconcile medications"** — then SILENCE ~20–30s, until the tile **refused** shows **1** and a purple card appears.
15. `PHONE` — pick it up, pull down to refresh Google Calendar, turn the screen to the camera.
16. **"Real appointments, in my actual phone's calendar. Not a screenshot — the fleet owns a calendar, it is shared to my account, and it writes through the Calendar API with the same idempotency keys as the clinical record."**
17. **"Remember this phone. When I kill the Scheduler in a minute — one event. Never two."**

**Scene 4 — the refusal**

18. **"And then it stops. One instruction on this sheet is genuinely ambiguous. Watch what it did with it."**
19. **"It refused. It did not guess. It assembled both readings — there they are, each citing the line it came from — and put a licensed human in front of the decision."**
20. **"That is the counter: refused, one. I put that number next to 'done autonomously' on purpose. Everyone here is optimising for how much their agents do alone. In medicine that is the wrong axis."**
21. `CLICK` **"dose schedule"** — wait ~20s — then `CLICK` **"daily check-in"** — wait ~20s *(you may talk over this one; watch the audit stream fill)*
22. **"A refusal is only worth something if the rest of the fleet respects it."**

**Scene 5 — the family page** *(switch Window A to /today)*

23. **"The Pharmacist built the day — real clock times. And amlodipine is held. Not dropped — held, at the bottom: 'don't take this one until you hear back.' Scheduling a disputed drug would be a clinical decision made silently by the agent least qualified to make it."**
24. **"And the Coach gets one question a day. Here is what it chose: '___'."** *(read the question off the screen)* **"It chose the question whose answer would help the clinician settle the open decision. Nobody wired these three agents together."** *(optional: press ▶ listen — the fleet asks out loud)*

**Scene 6 — the kill** *(switch Window A to /console/drill)*

25. **"Everything so far was the happy path. Let me break it. This panel kills a real worker process — no cleanup, no graceful shutdown. And the Scheduler no longer even runs on this service — it runs on its own."**
26. `CLICK` **"arm"** on the **Scheduler** row, then `CLICK` **"Start a task"**.
27. Switch Window A to **/console** — then SILENCE ~25s. Watch for: **DOWN** (red block) → **REDO** → a **new worker id** → **SKIP**.
28. **"The process is gone. Nothing caught that. The message was never acknowledged, so Pub/Sub redelivered it, Cloud Run supplied a fresh container — look at the worker id, different process — and the step it had already finished says SKIP. Skipped, not repeated."**
29. `PHONE` — refresh the calendar again, show the camera.
30. **"One appointment in the clinical record. One event on the phone. Never two of either — the idempotency key is written into both external systems. At-least-once delivery plus idempotent steps is effectively-once. There is no exactly-once, and I am not going to claim there is."**
31. **"And the red gap stays in the audit trail permanently. In a regulated domain, the scar is the evidence."**

**Scene 7 — escalation, then restraint** *(still on /console)*

32. **"Monitoring has been armed since minute one — against the red flags printed on this document. Here is a message from his daughter."**
33. `CLICK` **"report: chest pain"** — SILENCE ~25s, until the amber **ESCALATED** card appears with a **5:00** clock.
34. **"Paged. Note what it did not do — it did not treat, did not advise, did not reassure her. It put a clinician on it and started a five-minute clock. And that card is the one kind of task no agent can close."**
35. `CLICK` **"acknowledge · Dr. Chen"** on the card. *(watch "closed by a human" go to 1)*
36. **"Now the harder one."**
37. `CLICK` **"report: lightheaded"** — SILENCE ~25s. **Nothing** appears in the queue; the answer is in the audit stream.
38. **"It decided a human was not needed — and wrote down its reason, the strongest argument against its own decision, and what would have changed its answer. Anything can be built to panic. Restraint is the expensive part — a monitor that escalates everything is ignored inside a week."**

**Scene 8 — scale** *(switch Window A to /console/fleets)*

39. **"One patient is a demo. Two hundred coloured squares is the easiest thing in the world to fake — so let me hand all two hundred of them real work."**
40. `CLICK` **"hand work to all 200"** — SILENCE while the grid turns green (~30s).
41. **"Every square is a real patient record in the Healthcare API. Click any of them and the fleet behind it is there. The patients are synthetic. The infrastructure is not."**
42. **"And nothing about this is cardiac-specific. Wherever a human being is handed a piece of paper and expected to execute it correctly for six weeks — this works."**

**Scene 9 — the close**

43. *(pick up the paper, hold it to the camera, same framing as the opening)*
44. **"The hospital saves your life. Then it hands you a piece of paper."**
45. **"We take it from there."**
46. *(three seconds of silence — then stop the recording. Do NOT say thank you.)*

---

# PART E — After the take (~15 minutes)

## E1 · Check it

Watch the video once. Confirm: opening silence held · the parse landed ·
phone shown twice · DOWN→SKIP visible in scene 6 · ended on silence.

## E2 · Upload to YouTube

1. Go to https://studio.youtube.com (any of your Google accounts works).
2. Click **CREATE** (top right) → **Upload videos** → pick your recording
   (QuickTime saved it — usually on the Desktop, ending `.mov`).
3. Title: `VitaHome — live demo` . Click **Next, Next, Next**.
4. On **Visibility** choose **Unlisted** (NOT Private). Click **Save**.
5. Click **Copy video link**.

## E3 · Put it in Devpost and submit

1. Go to: https://devpost.com/submit-to/30845-all-things-agentic-hackathon/manage/submissions
2. Click your **VitaHome** draft → **Project details**.
3. Scroll to **Video demo link** → paste the YouTube link → click
   **Save & continue**.
4. Click the **Submit** step → press the **Submit** button.

Done. You can still edit anything until August 31.
