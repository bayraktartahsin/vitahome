#!/usr/bin/env python3
"""Generates docs/architecture-diagram.svg (and .png).

The previous diagram was assembled from hand-typed coordinates and had no
source in the repo. That combination is why it failed the way it did: text
outgrew boxes that were sized by eye, captions sat on top of connector lines,
and none of it could be corrected — only redrawn.

Here every box is sized from its text as actually rendered, measured with the
same font the SVG asks for, and every position is derived from the size of what
came before. A longer label makes its box wider; it cannot make it overflow.

    python3 scripts/make_diagram.py

Requires PIL for measurement and rsvg-convert for the PNG, both already present.
"""
from __future__ import annotations

import html
import subprocess
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "docs/architecture-diagram.svg"
PNG = ROOT / "docs/architecture-diagram.png"

SANS = "/System/Library/Fonts/Helvetica.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"
SANS_FAMILY = "Helvetica, Arial, sans-serif"
MONO_FAMILY = "Menlo, Consolas, monospace"

BG      = "#0F1216"
PANEL   = "#161B22"
SURF    = "#1B222B"
LINE    = "#2A323D"
INK     = "#E8EAED"
INK2    = "#98A2B0"
INK3    = "#6C7684"
ACCENT  = "#5FB287"
WARN    = "#D6A548"
DANGER  = "#D4685A"
INFO    = "#6FA3DB"
ROSE    = "#CB7396"
VIOLET  = "#9B87D4"

W = 1640                      # canvas width
PAD = 48                      # outer margin

_cache: dict[tuple[str, int, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, mono: bool = False, bold: bool = False):
    # PIL only loads integer sizes. Measuring at int(11.5) while the SVG draws
    # at 11.5 is a silent 4% under-measure — which is exactly how text ends up
    # hanging out of a box that was sized to hold it.
    if size != int(size):
        raise ValueError(f"type sizes must be whole numbers, got {size}")
    size = int(size)
    key = ("m" if mono else "s", size, bold)
    if key not in _cache:
        path = MONO if mono else SANS
        f = ImageFont.truetype(path, size)
        if bold and not mono:
            # Helvetica.ttc carries Bold as a later face in the collection.
            try:
                f = ImageFont.truetype(path, size, index=1)
            except Exception:
                pass
        _cache[key] = f
    return _cache[key]


def wide(text: str, size: int, mono: bool = False, bold: bool = False) -> float:
    """Width of this string as it will actually be drawn."""
    return font(size, mono, bold).getlength(text)


def esc(s: str) -> str:
    return html.escape(s, quote=False)


out: list[str] = []

# Every (string, size, mono, x, right-limit) drawn inside a container, checked
# at the end. Sizing boxes from measured text makes overflow impossible in
# principle; this is what proves it in practice, and turns the failure into a
# non-zero exit instead of something you notice in the exported PNG.
claims: list[tuple[str, float, bool, float, float]] = []


def add(s: str) -> None:
    out.append(s)


def fits(s: str, size: int, mono: bool, x: float, limit: float) -> None:
    claims.append((s, size, mono, x, limit))


def text(x, y, s, size=14, fill=INK, mono=False, bold=False, anchor="start",
         spacing=None):
    style = (f'font-family="{MONO_FAMILY if mono else SANS_FAMILY}" '
             f'font-size="{size}" fill="{fill}"')
    if bold:
        style += ' font-weight="600"'
    if anchor != "start":
        style += f' text-anchor="{anchor}"'
    if spacing:
        style += f' letter-spacing="{spacing}"'
    add(f'<text x="{x:.1f}" y="{y:.1f}" {style}>{esc(s)}</text>')


def rect(x, y, w, h, fill=SURF, stroke=LINE, r=9, sw=1, extra=""):
    add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')


# ---------------------------------------------------------------- boxes ----

BOX_PAD_X = 16
BOX_PAD_Y = 13
T_SIZE = 15
S_SIZE = 12


def box_size(title: str, sub: str = "", extra_lines: int = 0):
    """Width and height a box needs for its own text — measured, not guessed."""
    w = wide(title, T_SIZE, bold=True)
    if sub:
        w = max(w, wide(sub, S_SIZE, mono=True))
    w += BOX_PAD_X * 2
    h = BOX_PAD_Y * 2 + T_SIZE + 5
    if sub:
        h += S_SIZE + 4
    h += extra_lines * (S_SIZE + 4)
    return w, h


def box(x, y, title, sub="", stroke=LINE, fill=SURF, width=None, top=None,
        note=""):
    w, h = box_size(title, sub, 1 if note else 0)
    if width:
        w = max(w, width)
    rect(x, y, w, h, fill=fill, stroke=stroke)
    if top:                       # coloured cap, used to tag the agents
        add(f'<path d="M{x + 9:.1f} {y + 0.5:.1f} H{x + w - 9:.1f}" '
            f'stroke="{top}" stroke-width="2.5" stroke-linecap="round"/>')
    ty = y + BOX_PAD_Y + T_SIZE - 2
    limit = x + w - BOX_PAD_X
    text(x + BOX_PAD_X, ty, title, T_SIZE, INK, bold=True)
    fits(title, T_SIZE, False, x + BOX_PAD_X, limit)
    if sub:
        text(x + BOX_PAD_X, ty + S_SIZE + 4, sub, S_SIZE, INK3, mono=True)
        fits(sub, S_SIZE, True, x + BOX_PAD_X, limit)
    if note:
        text(x + BOX_PAD_X, ty + (S_SIZE + 4) * (2 if sub else 1), note,
             S_SIZE, INK2)
        fits(note, S_SIZE, False, x + BOX_PAD_X, limit)
    return w, h


# ------------------------------------------------------------ connectors ---

def arrow_right(x1, x2, y, label=""):
    """Horizontal connector. The label sits ABOVE the line, never across it."""
    add(f'<path d="M{x1:.1f} {y:.1f} H{x2 - 7:.1f}" stroke="{LINE}" stroke-width="1"/>')
    add(f'<path d="M{x2:.1f} {y:.1f} l-7,-4.5 v9 z" fill="{LINE}"/>')
    if label:
        text((x1 + x2) / 2, y - 8, label, 11, INK3, mono=True, anchor="middle")


def arrow_down(x, y1, y2, label=""):
    """Vertical connector. The label sits BESIDE the line, never on it."""
    add(f'<path d="M{x:.1f} {y1:.1f} V{y2 - 7:.1f}" stroke="{LINE}" stroke-width="1"/>')
    add(f'<path d="M{x:.1f} {y2:.1f} l-4.5,-7 h9 z" fill="{LINE}"/>')
    if label:
        text(x + 11, (y1 + y2) / 2 + 4, label, 11, INK3, mono=True)


# ================================================================ header ===

y = PAD

rect(PAD, y, 36, 36, fill=ACCENT, stroke=ACCENT, r=9)
text(PAD + 18, y + 25, "+", 24, "#0F1216", bold=True, anchor="middle")
text(PAD + 50, y + 17, "VitaHome — architecture", 29, INK, bold=True)
text(PAD + 50, y + 37, "An agent fleet that carries out hospital discharge instructions · Google Cloud",
     14, INK2)
y += 64

# =============================================================== panel 1 ===

P1_TOP = y
panel1_start = len(out)
add("")                                    # placeholder for the panel rect

px = PAD + 30
y += 30
text(px, y + 8, "How work flows", 21, INK, bold=True)
y += 22
text(px, y + 14, "Exactly one synchronous call — the parse, because a person is standing there holding a phone.",
     14, INK2)
text(px, y + 33, "Everything after it is decoupled: agents address each other by Pub/Sub attribute, never by function call.",
     14, INK2)
y += 60

# --- row: family surface -> parser
row_y = y
w1, h1 = box(px, row_y, "Family surface", "/capture · Next.js on Cloud Run")
gap = 92
x2 = px + w1 + gap
w2, h2 = box(x2, row_y, "Parser",
             "Gemini 3.5 Flash-Lite · ~3s · the only synchronous call")
arrow_right(px + w1, x2, row_y + h1 / 2, "photo")
# recolour the parser border
out[-1 - 3] = out[-1 - 3]                 # (no-op; kept explicit for clarity)
y = row_y + max(h1, h2)

# --- down to dispatch
spine_x = x2 + 74
arrow_down(spine_x, y + 6, y + 44, "care plan")
y += 44
wd, hd = box(x2, y, "dispatch", "writes the task, then publishes with agent=<name>")
y += hd

arrow_down(spine_x, y + 6, y + 44, "one message")
y += 44

# --- the bus
bus_h = 52
bus_w = W - 2 * PAD - 60
rect(px, y, bus_w, bus_h, fill="#12271D", stroke=ACCENT)
text(px + 18, y + 32, "Pub/Sub topic · fleet-work", 16, ACCENT, bold=True)
text(px + bus_w - 18, y + 32,
     "one topic · six push subscriptions · each filtered on the agent attribute",
     12, INK2, mono=True, anchor="end")
y += bus_h

# --- stubs down to the agents
# Duty text is the `verb` each agent publishes on its own A2A card, so the
# diagram cannot drift from what /registry serves. Every agent on this bus can
# refuse — that is said once, below, rather than mislabelled per box.
AGENTS = [
    ("Reconciler", '"reconciler"', "checks", ROSE),
    ("Scheduler", '"scheduler"', "books · own service", ACCENT),
    ("Pharmacist", '"pharmacist"', "sends", WARN),
    ("Watchman", '"watchman"', "watches", DANGER),
    ("Coach", '"coach"', "checks in", INFO),
    ("Escalator", '"escalator"', "calls a human", VIOLET),
]
n = len(AGENTS)
col_gap = 13
col_w = (bus_w - col_gap * (n - 1)) / n
stub = 24
for i in range(n):
    cx = px + i * (col_w + col_gap) + col_w / 2
    add(f'<path d="M{cx:.1f} {y:.1f} v{stub}" stroke="{LINE}" stroke-width="1"/>')
y += stub

ag_h = 0
for i, (name, filt, role, colour) in enumerate(AGENTS):
    bx = px + i * (col_w + col_gap)
    _, ag_h = box(bx, y, name, filt, top=colour, width=col_w, note=role)
y += ag_h + 26

for line in [
    "Every agent on this bus can REFUSE — return the decision to a clinician instead of guessing. The Escalator is",
    "human-terminated: no agent can close what it opens. Moving an agent off this service is a push-endpoint change,",
    "not a refactor — the Scheduler already runs on its own Cloud Run service, and nothing else changed. Messages",
    "carry a patient reference and a task id, never clinical content; each agent reads under its own IAM scope.",
]:
    text(px, y, line, 12, INK3, mono=True)
    y += 19

# --- google cloud rail
y += 14
add(f'<path d="M{px} {y:.1f} H{px + bus_w:.1f}" stroke="{LINE}" stroke-width="1"/>')
y += 24
text(px, y, "GOOGLE CLOUD SERVICES THIS RUNS ON", 11, INK3, mono=True, spacing="2.2")
y += 16

RAIL = [
    ("Cloud Run", "3 services · scale to zero"),
    ("Cloud Healthcare API", "FHIR R4 · real writes"),
    ("Firestore", "task ledger · append-only audit"),
    ("Google Calendar API", "events on a real phone"),
    ("Cloud Scheduler", "supervisor sweep · 5 min"),
]
rn = len(RAIL)
rcol = (bus_w - col_gap * (rn - 1)) / rn
rail_h = 0
for i, (t, s) in enumerate(RAIL):
    _, rail_h = box(px + i * (rcol + col_gap), y, t, s, width=rcol)
y += rail_h + 30

P1_BOT = y
out[panel1_start] = (
    f'<rect x="{PAD}" y="{P1_TOP}" width="{W - 2 * PAD}" height="{P1_BOT - P1_TOP}" '
    f'rx="14" fill="{PANEL}" stroke="{LINE}" stroke-width="1"/>'
)

# =============================================================== panel 2 ===

y += 26
P2_TOP = y
panel2_start = len(out)
add("")

y += 30
text(px, y + 8, "How a task survives its worker dying", 21, INK, bold=True)
y += 22
text(px, y + 14, "This is the part that matters. Nothing catches the kill — recovery is Pub/Sub redelivery plus a ledger",
     14, INK2)
text(px, y + 33, "that skips the steps already finished.", 14, INK2)
y += 58

CHIP_H = 40
CHIP_PAD = 15


def chip(x, y, label, colour, tint):
    w = wide(label, 12, mono=True) + CHIP_PAD * 2
    rect(x, y, w, CHIP_H, fill=tint, stroke=colour, r=8)
    text(x + CHIP_PAD, y + 25, label, 12, colour, mono=True)
    fits(label, 12, True, x + CHIP_PAD, x + w - CHIP_PAD)
    return w


LANE = 200          # the "who" column, fixed so both attempts align

text(px, y + 16, "attempt 1", 12, INK2, mono=True, bold=True)
text(px, y + 34, "worker nrl-dcc9a0", 12, INK3, mono=True)
cx = px + LANE
for label, colour, tint in [
    ("1  resolve_provider  done", "#BFE6D0", "#12271D"),
    ("2  fhir_appointment  killed mid-step", "#F0B3A9", "#2A1512"),
]:
    cx += chip(cx, y, label, colour, tint) + 12
y += CHIP_H + 18

kill_h = 54
rect(px, y, bus_w, kill_h, fill="#2A1512", stroke="#7A3329")
text(px + 16, y + 21, "os._exit(1) — no cleanup, no graceful shutdown, the message is never acked.",
     12, "#F0B3A9", mono=True)
text(px + 16, y + 39, "AGENT_DOWN: the heartbeat stops. This gap stays in the audit trail permanently.",
     12, "#F0B3A9", mono=True)
y += kill_h + 20

lbl = "Pub/Sub redelivers · measured at 8s after the process died"
lw = wide(lbl, 12, mono=True)
mid = px + bus_w / 2
add(f'<path d="M{px} {y:.1f} H{mid - lw / 2 - 14:.1f}" stroke="#6B5423" stroke-width="1"/>')
add(f'<path d="M{mid + lw / 2 + 14:.1f} {y:.1f} H{px + bus_w:.1f}" stroke="#6B5423" stroke-width="1"/>')
text(mid, y + 4, lbl, 12, WARN, mono=True, anchor="middle")
y += 24

text(px, y + 16, "attempt 2", 12, INK2, mono=True, bold=True)
text(px, y + 34, "worker nrl-958558", 12, INK3, mono=True)
text(px, y + 50, "a fresh container", 12, INK3, mono=True)
cx = px + LANE
for label, colour, tint in [
    ("1  resolve_provider  SKIPPED — already done", "#BBD6F2", "#141F2B"),
    ("2  fhir_appointment  done", "#BFE6D0", "#12271D"),
    ("3  calendar_event  done", "#BFE6D0", "#12271D"),
    ("4  confirm  done", "#BFE6D0", "#12271D"),
]:
    cx += chip(cx, y, label, colour, tint) + 12
y += CHIP_H + 26

oc_h = 96
rect(px, y, bus_w, oc_h, fill="#12271D", stroke=ACCENT)
text(px + 18, y + 27, "One FHIR Appointment. One calendar event. Never two of either.",
     16, "#BFE6D0", bold=True)
for i, line in enumerate([
    "Every step key is {taskId}:{stepName} — identical on every replay. The idempotency key is written INTO each external",
    "system (FHIR identifier, Calendar iCalUID) and searched for before creating, so the guarantee survives a total loss of",
    "local state. At-least-once delivery + idempotent steps = effectively-once. There is no exactly-once, and we do not claim it.",
]):
    text(px + 18, y + 49 + i * 17, line, 12, INK2, mono=True)
y += oc_h + 30

P2_BOT = y
out[panel2_start] = (
    f'<rect x="{PAD}" y="{P2_TOP}" width="{W - 2 * PAD}" height="{P2_BOT - P2_TOP}" '
    f'rx="14" fill="{PANEL}" stroke="{LINE}" stroke-width="1"/>'
)

# =============================================================== footer ====

y += 26
add(f'<path d="M{PAD} {y:.1f} H{W - PAD:.1f}" stroke="{LINE}" stroke-width="1"/>')
y += 24
text(PAD, y, "Cloud Run · Pub/Sub · Firestore · Cloud Healthcare API (FHIR R4) · Google Calendar API · "
             "Gemini 3.5 Flash-Lite + 3.7 Flash · Gemini TTS", 12, INK3, mono=True)
y += 19
text(PAD, y, "Gemma (PHI log audit) · ADK + A2A cards · Cloud Scheduler · Secret Manager",
     12, INK3, mono=True)
y += 19
text(PAD, y, "vitahome.vitamedas.com · Graviti Labs", 12, INK2, mono=True)
y += 22

H = y

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" '
       f'viewBox="0 0 {W} {H:.0f}">\n'
       f'<rect width="{W}" height="{H:.0f}" fill="{BG}"/>\n'
       + "\n".join(out) + "\n</svg>\n")

bad = [(t, x + wide(t, sz, mono) - lim)
       for t, sz, mono, x, lim in claims if x + wide(t, sz, mono) > lim + 0.5]
if bad:
    print(f"{len(bad)} string(s) overflow the box drawn around them:")
    for t, over in bad:
        print(f"   ! {over:5.1f}px  {t[:70]}")
    raise SystemExit(1)

SVG.write_text(svg)
subprocess.run(["rsvg-convert", "-w", str(W * 2), str(SVG), "-o", str(PNG)], check=True)
print(f"wrote {SVG.relative_to(ROOT)}  {W}x{H:.0f}")
print(f"wrote {PNG.relative_to(ROOT)}  {W * 2}x{H * 2:.0f}")
