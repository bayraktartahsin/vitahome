#!/usr/bin/env python3
"""Builds the recording guide: docs/RECORD-NOW.pdf and docs/RECORD-NOW.md.

One generator, two outputs, so the printed guide and the repo copy cannot say
different things. The spoken lines are read out of web/lib/autopilot.ts, which
is what the Director actually displays — a rehearsal sheet that has drifted
from the teleprompter teaches the wrong words.

Written plainly on purpose. The previous version leaned on typographic marks —
arrows, middots, bold-inside-backticks — and a reader who is about to record a
one-take video should not have to decode punctuation to find out which key to
press. Every command stands alone on its own line with nothing else in the box.

    python3 scripts/make_guide.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pdfwrite import Pdf, width, wrap        # noqa: E402

# ── palette ────────────────────────────────────────────────────────────────
INK      = (0.10, 0.11, 0.13)
INK2     = (0.38, 0.41, 0.46)
RULE     = (0.85, 0.86, 0.88)
BOXBG    = (0.955, 0.957, 0.965)
BOXBAR   = (0.20, 0.45, 0.32)
SAYBG    = (0.97, 0.975, 0.96)
SAYBAR   = (0.18, 0.42, 0.30)
WARNBG   = (1.00, 0.965, 0.92)
WARNBAR  = (0.80, 0.55, 0.13)

PAGE_W, PAGE_H = 595.28, 841.89
L, R, TOP, BOT = 54, 54, 62, 62
COL = PAGE_W - L - R


# ── the spoken script, read from the Director's own source ─────────────────
def spoken() -> tuple[list[dict], str]:
    src = (ROOT / "web/lib/autopilot.ts").read_text()
    body = src.split("SCRIPT: Step[] = [")[1].split("\n];")[0]
    cues, total = [], 0
    for block in ("\n" + body).split("\n  {"):
        m_ms = re.search(r"ms:\s*(\d+)", block)
        if not m_ms:
            continue
        ms = int(m_ms.group(1))
        say = re.search(r'say:\s*"((?:[^"\\]|\\.)*)"', block)
        note = re.search(r'note:\s*"((?:[^"\\]|\\.)*)"', block)
        page = re.search(r'page:\s*"([^"]*)"', block)
        cues.append({
            "at": total,
            "ms": ms,
            "say": (say.group(1).replace('\\"', '"') if say else ""),
            "note": (note.group(1).replace('\\"', '"') if note else ""),
            "silent": "silent: true" in block,
            "phone": "phone: true" in block,
            "page": page.group(1) if page else "",
        })
        total += ms
    return cues, f"{total // 60000}:{round(total % 60000 / 1000):02d}"


CUES, RUNTIME = spoken()

PAGE_NAMES = {
    "/capture": "the photograph page",
    "/console": "the clinician console",
    "/today": "the family's day view",
    "/console/drill": "the chaos panel",
    "/console/fleets": "the 200-fleet grid",
    "__gateway__/health/deep": "the Google Cloud page (the address bar changes)",
}


# ── document model ─────────────────────────────────────────────────────────
# Each block is a tuple the renderer knows how to draw and the markdown writer
# knows how to spell. Keeping the content as data is what lets one source
# produce both files.
def build() -> list[tuple]:
    d: list[tuple] = []
    A = d.append

    A(("title", "How to record the VitaHome demo"))
    A(("lede", f"The app drives itself. You do not click anything while recording, "
               f"you do not change pages, and you do not watch a clock. You read one "
               f"large line at a time off a second screen. The whole thing runs "
               f"{RUNTIME}."))

    A(("h2", "Three rules you cannot break"))
    A(("rule", "1. The video must be 4 minutes or shorter. Only the first 4 minutes "
               "are judged. This script runs " + RUNTIME + "."))
    A(("rule", "2. Do not edit or cut the video afterwards. The judges score a live, "
               "unedited run. Record it in one go and upload it as it is."))
    A(("rule", "3. On YouTube choose Public. Not Unlisted, not Private. "
               "A link that is not public can be counted as no entry at all."))

    A(("h2", "About the commands in this guide"))
    A(("warn", "When you see a grey box, copy only the text inside the box. "
               "Do not type the word bash, and do not type anything else. "
               "The box holds one complete command, start to finish."))
    A(("p", "To run one: press the Command key and the Space bar together, type the "
            "word Terminal, and press Enter. Click into the Terminal window, paste "
            "the line, and press Enter again."))

    # ── PART 1 ────────────────────────────────────────────────────────────
    A(("h1", "Part 1. Set this up once"))
    A(("p", "About 15 minutes. You only ever do this once."))

    A(("h2", "1.1  Put the appointment calendar on your phone"))
    A(("p", "The calendar is already shared with tahsin@gravitilabs.com."))
    A(("step", "On your phone, open the Gmail app and switch to the "
               "tahsin@gravitilabs.com account."))
    A(("step", "Find the email from Google Calendar. Its subject contains "
               "VitaHome - appointments (demo)."))
    A(("step", "Tap Add this calendar. That is all."))
    A(("p", "If there is no such email, open this address on your phone while signed "
            "in as tahsin@gravitilabs.com, and tap Add:"))
    A(("cmd", "https://calendar.google.com/calendar/u/0/r?cid=NzEyNDFkMDAxMjNkOGE1MDE2OTkzZWVkNmQzODIyMTViN2Q1NDc4ZDJjMTQ0YjExYjJkMWViN2ZiNDJmODZiZEBncm91cC5jYWxlbmRhci5nb29nbGUuY29t"))
    A(("p", "If the calendar is added but stays empty: open the Google Calendar app, "
            "tap your profile picture at the top right, tap Settings, find "
            "VitaHome - appointments (demo) under tahsin@gravitilabs.com, and turn "
            "Sync on."))

    A(("h2", "1.2  Check that the calendar works"))
    A(("step", "On the Mac, open Chrome at vitahome.vitamedas.com/console"))
    A(("step", "Click the button that says: seed patient. "
               "Wait for the small grey line under the buttons to say done."))
    A(("step", "Click the button that says: book follow-ups. Wait about 15 seconds."))
    A(("step", "On your phone open Google Calendar, pull down to refresh, and look "
               "about a week ahead at 1 in the afternoon. You should see exactly "
               "three entries, on three different days:"))
    A(("bullet", "Cardiology follow-up, at Mercy General Heart Center"))
    A(("bullet", "Primary care follow-up, at Mercy General Family Medicine"))
    A(("bullet", "Cardiac rehab intake, at Mercy General Rehabilitation"))
    A(("p", "Open one of them. It names the doctor, the discharge instruction it came "
            "from, and the medical record it is linked to. If you can see these three, "
            "the calendar is finished forever."))

    A(("h2", "1.3  If the calendar ever fills up with old appointments"))
    A(("p", "Every rehearsal books real appointments and they add up. Pressing the "
            "reset button before a take now deletes that patient's appointments too, "
            "so this normally takes care of itself. To wipe every appointment the "
            "system has ever created, run this command:"))
    A(("cmd", 'curl -s -X POST \\\n  "https://vitahome-gateway-205100594497.us-central1.run.app/demo/calendar/purge?includeUntagged=true"'))
    A(("p", "It only touches the calendar the app created and shared with you. It "
            "cannot see or change anything else in your Google account."))

    A(("h2", "1.4  You do not need a printed page"))
    A(("p", "An earlier version of this guide asked you to hold a printed discharge "
            "summary up to the camera. That was wrong: you are making a screen "
            "recording, so there is no camera in the picture and nobody would see "
            "the paper."))
    A(("p", "The document is now shown on the screen instead, on the first page of "
            "the app. The audience reads it there, tries to find the dangerous "
            "line, and fails - which is the whole point of the opening. There is "
            "nothing for you to hold and nothing to print."))
    A(("note", "If you want to see it before you record, open "
               "vitahome.vitamedas.com/capture and it is there."))

    A(("h2", "1.5  Get the screen recorder ready"))
    A(("step", "Press Command and Space together, type QuickTime Player, press Enter. "
               "If a file window opens, press the Escape key to close it."))
    A(("step", "In the menu bar at the top, click File, then New Screen Recording."))
    A(("step", "Click Options, and under Microphone choose MacBook Pro Microphone, "
               "or your headset if you are using one."))
    A(("step", "Do not start recording yet. You just needed to know where this is."))
    A(("p", "Optional, and worth doing: show your phone inside the video. Connect the "
            "iPhone to the Mac with a cable. In QuickTime click File, then New Movie "
            "Recording. Next to the red button click the small arrow and choose your "
            "iPhone under Camera. Drag that window into the bottom right corner and "
            "make it small. Leave it there. On the phone, open Google Calendar."))

    # ── PART 2 ────────────────────────────────────────────────────────────
    A(("h1", "Part 2. Before every take"))
    A(("p", "About 5 minutes, every time you record."))

    A(("h2", "2.1  Check that everything is healthy"))
    A(("p", "Run this command:"))
    A(("cmd", 'cd "/Users/bayraktar/Documents/New Apps/Hackhaton/vitahome" \\\n  && ./scripts/preflight.sh'))
    A(("p", "It takes about a minute. The last line must say: clear to record. "
            "If any line is red, send that red line to Claude before you continue."))

    A(("h2", "2.2  Open two windows"))
    A(("p", "There are two windows. Window B tells you what to say and is never "
            "recorded. Window A is the app itself, and it is the only thing you "
            "record. You open Window B now; Window A appears by itself in step 2.3."))
    A(("step", "Open a Chrome window at vitahome.vitamedas.com/director "
               "This is Window B. Put it on your second screen."))
    A(("step", "If you have no second screen, you will put Window A on the left two "
               "thirds of the screen and Window B on the right third. QuickTime lets "
               "you select just Window A's area when you record."))
    A(("warn", "Window B has to stay visible while you record. If it is completely "
               "hidden behind another window, the browser slows it down. The app "
               "corrects for this, but a visible window is one less thing to go wrong."))

    A(("h2", "2.3  Prepare the demo on Window B"))
    A(("p", "Press these buttons in order. After each one, wait for the small grey "
            "line underneath it to say done before pressing the next."))
    A(("step", "1 - reset"))
    A(("step", "2 - seed"))
    A(("step", "3 - seed 200 fleets   (this one takes about 20 seconds)"))
    A(("step", "4 - open the stage window"))
    A(("p", "A new window appears. That new window is Window A, the one you record. "
            "Move it to your main screen and make it large. Press Command and the "
            "plus key twice to zoom it in."))
    A(("p", "Underneath the buttons, Window B shows a Stage link box. Read it "
            "before you go any further. It tells you which window the app is "
            "about to drive."))
    A(("step", "Says driving /capture - one window: you are ready. The GO button "
               "turns on."))
    A(("step", "Says two or more windows answered: you have another copy of the "
               "app open. Either close it and press re-check, or click the one "
               "you are actually recording."))
    A(("step", "Says no window answering: open vitahome.vitamedas.com/capture in "
               "a second window yourself, then press re-check. It will be found."))
    A(("note", "Only the selected window takes commands; every other tab is a "
               "spectator. This matters more than it sounds. Before this check "
               "existed, a second open tab carried out every click a second time "
               "- every appointment was booked twice and arrived on the phone "
               "twice, and nothing said so until the calendar was looked at."))
    A(("warn", "Do not press GO yet."))

    A(("h2", "2.4  Silence everything"))
    A(("step", "On the Mac, click the clock at the top right and turn on Do Not Disturb."))
    A(("step", "On the phone, turn on Do Not Disturb. The calendar still updates."))
    A(("step", "Quit Slack, WhatsApp, Mail, and anything else that can pop up."))
    A(("step", "Put the phone on the desk with Google Calendar open and the screen unlocked."))

    # ── PART 3 ────────────────────────────────────────────────────────────
    A(("h1", "Part 3. Recording"))
    A(("step", "In QuickTime click File, then New Screen Recording. Drag to select "
               "Window A's area. Click Record."))
    A(("step", "On Window B press the button: 5 - GO"))
    A(("step", "Read the big line on Window B out loud. That is your whole job."))
    A(("p", "Window B shows one of three things above each line:"))
    A(("bullet", "say - read the large text out loud at a normal pace. "
                 "It moves on by itself when you finish."))
    A(("bullet", "silence - say nothing at all. The screen is doing the talking."))
    A(("bullet", "phone - then say - pull down to refresh the "
                 "calendar on your phone, then read the line. The mirrored phone "
                 "window is already inside the recording, so there is nothing "
                 "to hold up."))
    A(("p", "Smaller grey text underneath a line is an instruction for you. Never read "
            "it out loud."))
    A(("p", "If you cough or lose your place, press the Space bar to pause, and press "
            "it again to carry on. If you finish a line early, press the right arrow "
            "key to move on."))
    A(("step", "When the last line tells you to stop, stay silent for three seconds, "
               "then click the stop button in the menu bar at the top right of the screen."))
    A(("warn", "If something goes wrong while recording, say: and this is live, so "
               "let's watch it recover. Then keep going. The judges reward a live "
               "unedited run, so a visible recovery is worth more than starting again."))

    # ── PART 4 ────────────────────────────────────────────────────────────
    A(("h1", "Part 4. Every word you say, in order"))
    A(("p", f"There are {len(CUES)} steps and the whole run is {RUNTIME}. "
            f"Window B shows you each one, so you do not have to memorise any of it. "
            f"This list is here so you can practise."))

    for n, c in enumerate(CUES, 1):
        if c["page"]:
            A(("moves", "The screen moves by itself to " +
               PAGE_NAMES.get(c["page"], c["page"])))
        secs = f"{c['at'] // 60000}:{round(c['at'] % 60000 / 1000):02d}"
        if c["silent"]:
            A(("silence", n, secs, f"Say nothing for {round(c['ms'] / 1000)} seconds.",
               c["note"]))
        else:
            label = "Pick up the phone, then say:" if c["phone"] else "Say:"
            A(("say", n, secs, label, c["say"], c["note"]))

    # ── PART 5 ────────────────────────────────────────────────────────────
    A(("h1", "Part 5. Upload and submit"))
    A(("h2", "5.1  Check the file first"))
    A(("p", "The recording is saved in your Movies folder or on the Desktop. "
            "Open it and check all four of these:"))
    A(("bullet", "It is shorter than 4 minutes. This script is " + RUNTIME +
                 ". If yours is longer, you paused during the take - record it again "
                 "rather than cutting anything out."))
    A(("bullet", "You can hear your voice clearly the whole way through."))
    A(("bullet", "There is a moment where the web address at the top of the browser "
                 "ends in run.app. That is the proof the judges need that it runs on "
                 "Google Cloud."))
    A(("bullet", "Window B, the one with your lines on it, is not visible anywhere "
                 "in the video."))

    A(("h2", "5.2  Put it on YouTube"))
    A(("step", "Go to studio.youtube.com, click Create, then Upload videos, "
               "and drag the file in."))
    A(("step", "For the title, use this:"))
    A(("cmd", "VitaHome - an agent fleet that executes hospital discharge instructions"))
    A(("step", "For the description, use this:"))
    A(("block", "VitaHome is a fleet of seven agents that carries out the instructions "
                "on a hospital discharge summary - reconciling medications, booking "
                "follow-ups, building the dose schedule, and watching for the warning "
                "signs printed on the page. The agents can refuse: where an instruction "
                "can be read two ways, the fleet stops and puts a clinician in front of "
                "the decision instead of guessing.\n\n"
                "Built on Google Cloud: Cloud Run, Pub/Sub, Firestore, the Cloud "
                "Healthcare API (FHIR R4), the Google Calendar API, and Gemini.\n\n"
                "Everything in this video is a live, unedited run against the deployed "
                "system. The patients are synthetic; the infrastructure is not."))
    A(("step", "Where it asks about audience, choose: No, it's not made for kids."))
    A(("step", "Click Next three times until you reach Visibility."))
    A(("step", "Choose Public. Not Unlisted. Not Private."))
    A(("step", "Click Publish, then copy the link."))

    A(("h2", "5.3  Put the link into Devpost"))
    A(("step", "Open your submission page on Devpost."))
    A(("step", "Paste the YouTube link into the video field."))
    A(("step", "Check the Try it out link still says vitahome.vitamedas.com"))
    A(("step", "Click Save, then click Submit. Only you can press Submit - nobody "
               "else can do that step for you."))
    return d


# ── PDF rendering ──────────────────────────────────────────────────────────
def render_pdf(doc: list[tuple], out: Path) -> int:
    p = Pdf(PAGE_W, PAGE_H)
    y = TOP
    page_no = 1

    def footer() -> None:
        p.rect(L, PAGE_H - BOT + 18, COL, 0.6, RULE)
        p.text(L, PAGE_H - BOT + 32, "VitaHome - recording guide", "H", 8, INK2)
        w = width(f"page {page_no}", "H", 8)
        p.text(L + COL - w, PAGE_H - BOT + 32, f"page {page_no}", "H", 8, INK2)

    def space(need: float) -> None:
        nonlocal y, page_no
        if y + need > PAGE_H - BOT:
            footer()
            p.new_page()
            page_no += 1
            y = TOP

    for block in doc:
        kind = block[0]

        if kind == "title":
            space(70)
            p.text(L, y + 26, block[1], "HB", 23, INK)
            y += 44

        elif kind == "lede":
            lines_ = wrap(block[1], "H", 11.5, COL)
            space(len(lines_) * 16 + 12)
            for line in lines_:
                p.text(L, y + 11, line, "H", 11.5, INK2)
                y += 16
            y += 12

        elif kind == "h1":
            space(190)
            y += 20
            p.rect(L, y, COL, 1.4, BOXBAR)
            y += 16
            p.text(L, y + 16, block[1], "HB", 17, INK)
            y += 30

        elif kind == "h2":
            space(132)
            y += 12
            p.text(L, y + 13, block[1], "HB", 12.5, INK)
            y += 22

        elif kind == "p":
            lines = wrap(block[1], "H", 11, COL)
            space(len(lines) * 15.5 + 7)
            for line in lines:
                p.text(L, y + 11, line, "H", 11, INK)
                y += 15.5
            y += 7

        elif kind in ("step", "bullet"):
            marker = "-" if kind == "bullet" else ">"
            lines = wrap(block[1], "H", 11, COL - 18)
            space(len(lines) * 15.5 + 5)
            for i, line in enumerate(lines):
                if i == 0:
                    p.text(L + 2, y + 11, marker, "HB", 11, BOXBAR)
                p.text(L + 18, y + 11, line, "H", 11, INK)
                y += 15.5
            y += 5

        elif kind == "rule":
            lines = wrap(block[1], "H", 11, COL - 22)
            space(len(lines) * 15.5 + 12)
            p.rect(L, y - 2, 2.5, len(lines) * 15.5 + 6, BOXBAR)
            for line in lines:
                p.text(L + 14, y + 11, line, "H", 11, INK)
                y += 15.5
            y += 10

        elif kind == "warn":
            lines = wrap(block[1], "H", 11, COL - 30)
            h = len(lines) * 15.5 + 16
            space(h + 10)
            p.rect(L, y, COL, h, WARNBG)
            p.rect(L, y, 3, h, WARNBAR)
            yy = y + 8
            for line in lines:
                p.text(L + 16, yy + 11, line, "H", 11, INK)
                yy += 15.5
            y += h + 12

        elif kind == "cmd":
            size = 8.5
            lines: list[str] = []
            for raw in block[1].split("\n"):
                if width(raw, "C", size) <= COL - 24:
                    lines.append(raw)
                    continue
                chars = int((COL - 24) / (size * 0.6))
                lines += [raw[i:i + chars] for i in range(0, len(raw), chars)]
            h = len(lines) * 13 + 18
            space(h + 10)
            p.rect(L, y, COL, h, BOXBG)
            p.rect(L, y, 3, h, BOXBAR)
            yy = y + 9
            for line in lines:
                p.text(L + 14, yy + 9, line, "C", size, INK)
                yy += 13
            y += h + 12

        elif kind == "block":
            for para in block[1].split("\n\n"):
                for line in wrap(para, "H", 10, COL - 24):
                    space(15)
                    p.text(L + 14, y + 10, line, "H", 10, INK2)
                    y += 14
                y += 6
            y += 8

        elif kind == "moves":
            # Keep this with the cue it introduces. Alone at the foot of a page
            # it reads as an instruction for the line above it, which is the
            # opposite of what it means.
            space(104)
            y += 6
            p.text(L, y + 10, block[1], "H", 9.5, BOXBAR)
            y += 16

        elif kind == "silence":
            _, n, at, text, note = block
            lines = wrap(text, "HB", 12, COL - 60)
            extra = wrap(note, "H", 9.5, COL - 60) if note else []
            h = len(lines) * 16 + len(extra) * 13 + 18
            space(h + 8)
            p.rect(L, y, COL, h, BOXBG)
            p.text(L + 12, y + 20, f"{n}", "HB", 12, INK2)
            p.text(L + 12, y + 34, at, "C", 7.5, INK2)
            yy = y + 10
            for line in lines:
                p.text(L + 48, yy + 12, line, "HB", 12, INK2)
                yy += 16
            for line in extra:
                p.text(L + 48, yy + 10, line, "H", 9.5, INK2)
                yy += 13
            y += h + 8

        elif kind == "say":
            _, n, at, label, text, note = block
            lines = wrap(text, "HB", 12.5, COL - 60)
            extra = wrap(note, "H", 9.5, COL - 60) if note else []
            h = 14 + 13 + len(lines) * 17 + len(extra) * 13 + 12
            space(h + 8)
            p.rect(L, y, COL, h, SAYBG)
            p.rect(L, y, 3, h, SAYBAR)
            p.text(L + 12, y + 20, f"{n}", "HB", 12, SAYBAR)
            p.text(L + 12, y + 34, at, "C", 7.5, INK2)
            p.text(L + 48, y + 18, label, "H", 9.5, INK2)
            yy = y + 26
            for line in lines:
                p.text(L + 48, yy + 13, line, "HB", 12.5, INK)
                yy += 17
            for line in extra:
                p.text(L + 48, yy + 11, line, "H", 9.5, INK2)
                yy += 13
            y += h + 8

    footer()
    p.save(out)
    return page_no


# ── markdown rendering ─────────────────────────────────────────────────────
def render_md(doc: list[tuple], out: Path) -> None:
    o: list[str] = ["<!-- Generated by scripts/make_guide.py - do not edit by hand. -->",
                    ""]
    for b in doc:
        k = b[0]
        if k == "title":      o += [f"# {b[1]}", ""]
        elif k == "lede":     o += [b[1], ""]
        elif k == "h1":       o += ["", f"## {b[1]}", ""]
        elif k == "h2":       o += [f"### {b[1]}", ""]
        elif k == "p":        o += [b[1], ""]
        elif k == "step":     o += [f"- {b[1]}"]
        elif k == "bullet":   o += [f"  - {b[1]}"]
        elif k == "rule":     o += [f"> {b[1]}", ""]
        elif k == "warn":     o += ["", f"**{b[1]}**", ""]
        elif k == "cmd":      o += ["", "```", b[1], "```", ""]
        elif k == "block":    o += ["", "```", b[1], "```", ""]
        elif k == "moves":    o += ["", f"*{b[1]}*", ""]
        elif k == "silence":
            o += [f"**{b[1]}.** ({b[2]}) {b[3]}" + (f"  \n    {b[4]}" if b[4] else ""), ""]
        elif k == "say":
            o += [f"**{b[1]}.** ({b[2]}) {b[3]}  ",
                  f'   **"{b[4]}"**' + (f"  \n   *{b[5]}*" if b[5] else ""), ""]
    out.write_text("\n".join(o) + "\n")


if __name__ == "__main__":
    doc = build()
    pages = render_pdf(doc, ROOT / "docs/RECORD-NOW.pdf")
    render_md(doc, ROOT / "docs/RECORD-NOW.md")
    print(f"wrote docs/RECORD-NOW.pdf   ({pages} pages, {len(CUES)} spoken steps, {RUNTIME})")
    print(f"wrote docs/RECORD-NOW.md")
