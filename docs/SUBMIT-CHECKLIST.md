# Submission checklist — the last mile, in order

Everything the machine can do is done. What remains needs your hands, your
voice, or your Devpost login. Total time: about two hours, most of it the video.

## 1 · Freeze (5 min)

```bash
./scripts/preflight.sh && ./scripts/fullrun.sh
```

Both green → stop changing code. Every edit after this point risks more than it
buys.

## 2 · Record the video (60–90 min including rehearsal)

- Script: `docs/VIDEO-SCRIPT.md`. Rehearse the full take twice before recording.
- Print the discharge summary — the paper prop is the opening and closing shot.
  The text is in `backend/app/sim/hero_patient.py`.
- One take, no edits. If something breaks, narrate it and keep going — the
  script has a line for exactly that.
- Read numbers off the screen, never from memory (the parse timer, the SLA
  clock, the worker ids).
- Upload to YouTube as **unlisted**, then paste the URL into the form.

## 3 · Fill the Devpost form (15 min)

Every field is pre-written in `docs/SUBMISSION.md` — paste in order:

- **Project name / tagline / elevator pitch** → top of the file
- **"About the project"** → the long body (problem → what it does → the three
  things worth looking at → how we built it → challenges → what's next)
- **Built with** → `python · typescript · fastapi · nextjs · cloud-run ·
  pub-sub · firestore · cloud-healthcare-api · gemini · gemma ·
  agent-development-kit · cloud-scheduler · secret-manager`
- **Links** → the Try-it table (live app, drill, fleets, architecture,
  registry, repo)
- **Track** → The Fortified Enterprise Fleet. Also tick **Startup Excellence**
  (Graviti Labs is incorporated).
- **Video** → your YouTube URL from step 2

Use the publisher identity for any name/email fields: **Tahsin Bayraktar ·
info@gravitilabs.com · Graviti Labs**.

## 4 · After submitting (5 min)

- Post nothing publicly until results — the copy in `docs/SOCIAL.md` is ready
  for afterwards.
- Leave the deployment exactly as it is. It costs ~nothing idle, judges may
  click at any hour, and cold start is sub-second.
- If you ever want the demo endpoints locked (after judging):
  `gcloud run services update vitahome-gateway --region us-central1 --update-env-vars DEMO_KEY=<something>`

## Do not

- Do not re-record the video to chase a cleaner take of a working demo — a
  survived hiccup is worth more than polish.
- Do not edit code after step 1 without re-running `fullrun.sh`.
- Do not add features. The audit found the system complete; the remaining
  points live in the video, not the code.
