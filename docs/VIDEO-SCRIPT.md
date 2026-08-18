# Recording the demo — the simple version

You do three things, in this order:

1. **One-time setup** (~10 minutes, only once)
2. **Pre-take checklist** (~3 minutes, every time)
3. **The take** (~4½ minutes) — a teleprompter tells you every word and every click

The teleprompter is built into the app: **open `/director` on the web app.**
It shows one cue at a time in huge text — `SAY` means read it aloud, `DO` means
one click, `SILENCE` means say nothing. Press the **right-arrow key** to move to
the next cue. You never have to remember anything.

---

## 1 · One-time setup

### A. Put the fleet's calendar on your phone (5 min)

The demo shows appointments appearing in your phone's Google Calendar. For that,
your phone needs the fleet's calendar once.

**The calendar is shared with `info@gravitilabs.com`.** If your phone's Google
Calendar is signed into a different Gmail, tell Claude that address first — it
is a one-line change.

On your **phone**:

1. Open the **Gmail** app for `info@gravitilabs.com`. Find the email from
   Google Calendar — subject like *"…has shared a calendar with you"*
   ("VitaHome — appointments (demo)"). Tap **Add this calendar**. Done — skip
   to step 4.
2. No email? Open this link in your phone's browser (signed in as
   info@gravitilabs.com):

   https://calendar.google.com/calendar/u/0/r?cid=NzEyNDFkMDAxMjNkOGE1MDE2OTkzZWVkNmQzODIyMTViN2Q1NDc4ZDJjMTQ0YjExYjJkMWViN2ZiNDJmODZiZEBncm91cC5jYWxlbmRhci5nb29nbGUuY29t

   When it asks to add "VitaHome — appointments (demo)", tap **Add**.
3. Still nothing? Do it on a computer at calendar.google.com — the calendar is
   already under **"Other calendars"** on the left. Then on the phone:
   Google Calendar app → **☰ menu** → **Settings** → under info@gravitilabs.com
   find **VitaHome — appointments (demo)** → turn **Sync ON**.
4. **Test it:** on your Mac open the app → `/console` → click **seed patient**,
   then **book follow-ups**. Wait 20 seconds. On the phone, open Google
   Calendar and **pull down to refresh** — appointments appear next week
   (around Tue/Thu 10:00). If you see them, you are done forever.

### B. Print the paper prop (2 min)

Print [`docs/discharge-summary.txt`](discharge-summary.txt) — one page. This is
the paper you hold up at the start and the end.

### C. Know your recorder (2 min)

Use **QuickTime**, already on your Mac:

1. Open QuickTime Player → **File → New Screen Recording**.
2. Click **Options** → under Microphone pick your mic (MacBook microphone is fine).
3. Choose **Record Selected Window**... actually simplest: record the whole
   second screen/window area where the stage browser lives.
4. To stop: click the ⏺ stop icon in the menu bar.

Phone-in-frame moments: just hold the phone up to your Mac's camera? No — the
recording is your screen. **Two easy options, pick one:**

- **Easiest:** put your phone screen next to the browser using **QuickTime →
  File → New Movie Recording → camera dropdown → your iPhone** (connect by
  cable). Size that window small, park it in a corner of the stage screen. Your
  phone's screen is now visible inside the recording the whole time.
- Or skip the phone window and, at the phone moments, open
  calendar.google.com in a stage-browser tab instead — same calendar, still
  real, slightly less dramatic.

---

## 2 · Pre-take checklist — every time

In Terminal, inside the `vitahome` folder:

```bash
./scripts/preflight.sh
```

All green? Continue. Then arrange windows:

| Where | What |
|---|---|
| Screen/half you record | Browser window at the app, `/capture`, zoom 125% (Cmd +) |
| Screen/half you do NOT record | Second browser window at `/director` |
| Desk, in reach | Phone (calendar app open) + the printed paper |

On the `/director` page press **1 · reset**, then **2 · seed**, wait for each
"done". Turn on **Do Not Disturb** on Mac and phone. Close Slack/mail.

Do one silent practice run clicking through the director cues without
recording — 5 minutes, and the real take will feel easy.

---

## 3 · The take

1. Start the QuickTime recording.
2. On `/director`, press **Start**.
3. Do exactly what each cue says. **Right arrow** for the next cue.
   - `SAY` (white serif text) — read it out loud, word for word. Two cues ask
     you to read a number or a question **off the stage screen** — say whatever
     is actually there.
   - `DO` (amber text) — one action: a click on the stage window, or picking up
     the phone.
   - `SILENCE` (green text) — say nothing and let the screen work. This will
     feel too long. It is not. The silence is the proof.
4. The last cue says stop recording. Stop it.

**If something breaks mid-take: do not stop.** Say "and this is live, so let's
watch it recover" — the system genuinely recovers, and a survived hiccup is
worth more than a clean run. Only restart the take if the internet itself dies.

---

## 4 · After the take

1. Watch it once. Checklist: opening silence held · the parse landed · phone
   shown twice · the DOWN→SKIP sequence visible · ended on silence.
2. Upload to **YouTube** → visibility **Unlisted** (NOT private).
3. Copy the YouTube link → Devpost → **Project details** → paste into **Video
   demo link** → **Save & continue**.
4. Devpost → **Submit** step → submit. (You can still edit until the deadline.)

That's everything.
