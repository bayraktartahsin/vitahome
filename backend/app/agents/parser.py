"""📄 Parser — the document becomes a plan.

This is the beat the demo opens on: photograph a discharge summary and, in about
a second, get back every instruction on it **sorted by what happens if it is
missed**. Not by the order they appear on the page — by consequence.

That ordering is the entire product argument. A discharge summary lists the
fatal instruction seventh, in the same font as "no lifting over 10 lbs". The
document format actively hides the thing that matters. Re-ranking it is a small
piece of engineering and the reason a family catches the line they would
otherwise skim past on a third reading in a hospital corridor.

Three rules this agent is built around:

1. **Never invent an instruction.** Every returned item must quote text that is
   physically on the page. The line number is required for exactly this reason —
   it is checkable, and it makes the UI able to point at the source.
2. **Ambiguity is a finding, not a failure.** An instruction that reads two ways
   is returned *with both readings* and marked ambiguous. Downstream, the
   Reconciler refuses to act on it and hands a human the choice. A parser that
   resolves ambiguity by picking the likelier reading is the most dangerous
   component you could put in this system.
3. **Low confidence routes to a human.** Below ``parser_confidence_floor`` the
   instruction goes to the exception queue rather than into execution.

Synchronous on purpose. Everything else in the fleet is async over Pub/Sub, but
this one runs in the request because a human is standing there holding a phone,
and ~1s of waiting is the product.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..fleet import ledger
from ..integrations import gemini

log = logging.getLogger("vitahome.parser")

CRITICALITY = ["CRITICAL", "caution", "none"]
TYPES = ["medication", "medication_stop", "followup", "restriction", "red_flag", "other"]

# Enforced by the API. Everything the downstream fleet needs to act is required
# here, so a malformed extraction fails at the boundary instead of three agents
# later with a KeyError in a worker nobody is watching.
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "documentType": {"type": "string"},
        "patientName": {"type": "string"},
        "instructions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lineNo": {"type": "integer"},
                    "text": {"type": "string"},
                    "type": {"type": "string", "enum": TYPES},
                    "criticality": {"type": "string", "enum": CRITICALITY},
                    "why": {"type": "string"},
                    "confidence": {"type": "number"},
                    "ambiguous": {"type": "boolean"},
                    "readings": {"type": "array", "items": {"type": "string"}},
                    "specialty": {"type": "string"},
                    "daysOut": {"type": "integer"},
                    "drug": {"type": "string"},
                    "dose": {"type": "string"},
                    "flags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["lineNo", "text", "type", "criticality", "confidence"],
            },
        },
    },
    "required": ["documentType", "instructions"],
}

PROMPT = """You are extracting actionable instructions from a patient discharge document.

Return EVERY instruction the patient or their family is expected to carry out,
and nothing else. Do not summarise, and do not add anything that is not
physically written on the page.

ONE INSTRUCTION PER ACTION. A warning, dose, duration, or qualifier attached to
a medication is PART OF that medication's instruction, not a separate one. For
example "Ticagrelor 90 mg twice daily for 12 months" followed by "** DO NOT STOP
without speaking to cardiology **" is ONE instruction — the warning belongs to
the ticagrelor line and must be included in its text. Splitting it produces a
free-floating directive with no drug attached, which downstream agents cannot
act on safely.

Fields:

- lineNo: the number printed at the start of the line, exactly as given. If the
  document is an image with no numbering, count visible lines from 1.
- text: the instruction, quoted closely enough that a person can find it on the
  page. Include any attached warning.
- type:
    medication       start or continue taking something
    medication_stop  the document says to STOP taking something
    followup         an appointment that must be booked
    restriction      an activity limit
    red_flag         symptoms that mean return to hospital
    other            anything actionable that fits none of the above
  A "do not stop" warning is a medication, NOT a medication_stop. medication_stop
  means the patient should cease a drug. Getting this backwards is dangerous.

- criticality: judge ONLY by what happens if this instruction is MISSED.
    CRITICAL  missing it can kill or cause serious permanent harm within weeks.
              Typically antiplatelet/anticoagulant therapy after a stent,
              insulin, anti-rejection drugs, and the return-to-emergency symptom
              list. On a typical discharge summary this is 1-3 lines, rarely more.
    caution   missing it causes a meaningful setback, a missed diagnosis, or an
              avoidable readmission. Specialist follow-up after a cardiac event,
              a stop order that leaves the patient double-dosed.
    none      inconvenience, discomfort, or a minor delay. Most activity
              restrictions, most routine follow-up, most maintenance medication.
  Use all three levels. If everything on a page comes back CRITICAL or caution,
  the ranking carries no information and you have not done the job. Judge each
  line on its own worst case, not on the seriousness of the diagnosis.

- why: for CRITICAL only. One plain sentence a frightened family member would
  understand, saying what actually happens. No jargon, no hedging.

- confidence: 0-1, how sure you are that you READ THIS CORRECTLY — not how sure
  you are of the medicine. Clean typed text you can read without effort is
  0.95-0.99. Reserve 1.0 for nothing. Use 0.7-0.9 if the wording is loose or you
  inferred a field. Use below 0.6 if the text is smudged, cropped, handwritten,
  or partly guessed. An honest low number sends the line to a human, which is
  the correct outcome — an inflated one sends a guess into execution.

- ambiguous + readings: set ambiguous=true when THIS line on its own supports
  more than one reading that would lead to DIFFERENT actions, and list each
  reading. Do NOT pick the likelier one. A human decides. (Contradictions
  BETWEEN two different lines are not your job — extract both faithfully and
  the reconciliation stage will catch the conflict.)

- followup only: specialty (lowercase) and daysOut (integer days from discharge).
- medication and medication_stop only: drug and dose.
- red_flag only: flags, as a list of individual symptoms.

If this is not a medical document, set documentType to what it actually is and
return an empty instructions array. Never invent medical content from a
non-medical page."""


def _number_lines(text: str) -> str:
    """Prefix every line with its number before showing it to the model.

    Asking a model to count lines produces answers that drift by one or two
    between runs, which quietly breaks the "point at the source line" feature
    and makes the extraction unverifiable. Numbering is arithmetic — so we do it
    here, and the model only has to copy.
    """
    return "\n".join(f"{n:>3} | {line}" for n, line in enumerate(text.splitlines(), 1))


def _rank(ins: dict[str, Any]) -> tuple[int, float]:
    """Consequence first, then confidence. This is the re-ranking, and it is
    deliberately not the model's job — ordering must be deterministic and
    inspectable, not a thing the model felt like doing that run."""
    order = {"CRITICAL": 0, "caution": 1, "none": 2}
    return (order.get(ins.get("criticality", "none"), 2), -float(ins.get("confidence", 0)))


def parse(pid: str, *, text: str | None = None, image: bytes | None = None,
          mime_type: str = "image/jpeg") -> dict[str, Any]:
    """Extract a care plan and write it to the patient's fleet state."""
    if image is None and not (text or "").strip():
        raise gemini.ModelError("nothing to parse — provide an image or document text")

    # Text is pre-numbered so the model only has to copy; an image has nothing
    # to copy from, so it counts visible lines and the result is approximate.
    # The UI needs to know which, because "line 7" printed next to an
    # instruction is a promise you can check against the paper in your hand.
    exact = image is None
    prompt = (PROMPT if image is not None
              else f"{PROMPT}\n\n--- DOCUMENT (line numbers are given) ---\n{_number_lines(text)}")
    out, meta = gemini.generate_json(
        prompt, SCHEMA, model=settings.model_fast, image=image, mime_type=mime_type
    )

    raw = out.get("instructions") or []
    raw.sort(key=_rank)

    floor = settings.parser_confidence_floor
    instructions: list[dict[str, Any]] = []
    for n, ins in enumerate(raw, start=1):
        low = float(ins.get("confidence", 0)) < floor
        amb = bool(ins.get("ambiguous"))
        instructions.append({
            **ins,
            "id": f"i_{n:02d}",
            # Anything uncertain or double-readable is parked for a human before
            # it can be dispatched. "needs_human" is a first-class state, not an
            # error state — the exception queue is where it belongs.
            "status": "needs_human" if (low or amb) else "pending",
            "heldReason": ("confidence below floor" if low else
                           "instruction reads more than one way" if amb else None),
        })

    critical = [i["id"] for i in instructions if i.get("criticality") == "CRITICAL"]
    held = [i["id"] for i in instructions if i["status"] == "needs_human"]

    ledger.db().collection("patients").document(pid).set({
        "fleetState": "active",
        "carePlan": {
            "sourceDocument": text,
            "documentType": out.get("documentType"),
            "parsedAt": datetime.now(timezone.utc),
            "parserVersion": "parser-v1",
            "lineNumbersExact": exact,
            "parserModel": meta["model"],
            "parseLatencyMs": meta["latencyMs"],
            "instructions": instructions,
        },
    }, merge=True)

    ledger.audit(pid, "action", "parser",
                 f"parsed {len(instructions)} instructions in {meta['latencyMs']}ms — "
                 f"{len(critical)} critical, {len(held)} held for a human",
                 None, {"model": meta["model"], "latencyMs": meta["latencyMs"]})
    ledger.bump_ledger(pid, "autonomous")

    return {
        "patientId": pid,
        "documentType": out.get("documentType"),
        "instructions": instructions,
        "counts": {"total": len(instructions), "critical": len(critical),
                   "heldForHuman": len(held)},
        "lineNumbersExact": exact,
        "model": meta["model"],
        "latencyMs": meta["latencyMs"],
    }
