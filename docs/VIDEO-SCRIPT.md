# Recording the demo

**This file is superseded. Use [`RECORD-NOW.md`](RECORD-NOW.md).**

The demo is no longer driven by hand. The app drives itself: the Director page
navigates the recorded window and presses its buttons on cue, and the presenter
only reads the line on screen. There is nothing to click during a take and no
key to press between cues.

Two things changed that make the old instructions actively wrong:

- **The video may not exceed four minutes.** This guide described a 4½-minute
  take. The autopilot is timed to 3:52, and `scripts/time-script.mjs` fails the
  preflight if an edit pushes it over.
- **`DO` cues no longer exist.** Every click the old script asked for now
  happens automatically, so a rehearsal from this file would teach the wrong
  sequence.

The spoken script is generated from the Director itself into Part D of
`RECORD-NOW.md` by `scripts/render-script.mjs` — that is the one place the words
live, so the rehearsal sheet can never drift from the teleprompter.
