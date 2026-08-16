"""🚨 Escalator — decides whether a human is needed, and is the only agent a
human has to close out.

Two outcomes, and the second one is the harder engineering problem:

  escalate  page a clinician, start an SLA clock, and stop. The task stays open
            until a person resolves it. No agent can close it.
  stand down  record the finding, explain why no human was needed, complete.

Anything can be built to panic. A monitor that escalates everything is ignored
inside a week, and an ignored monitor is worse than no monitor — it converts a
gap in coverage into a false belief that coverage exists. So the restraint is
not a nicety here, it is the feature.

**The safety asymmetry.** The model advises; code decides — and the code is
allowed to override the model in exactly one direction. If the model says stand
down but the finding matches a red flag printed on the patient's own discharge
document, we escalate anyway. There is no path in this file where a model's
reassurance can suppress a documented red flag. That asymmetry is pinned by a
test, because it is the property that makes the restraint safe to ship.
"""
from __future__ import annotations

import logging
from typing import Any

from ..config import settings
from ..fleet import ledger
from ..fleet.runtime import Escalation, Refusal
from ..integrations import gemini

log = logging.getLogger("vitahome.escalator")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendEscalation": {"type": "boolean"},
        "urgency": {"type": "string", "enum": ["emergency", "urgent", "routine", "none"]},
        "rationale": {"type": "string"},
        "argumentsAgainst": {"type": "string"},
        "whatWouldChangeThis": {"type": "string"},
    },
    "required": ["recommendEscalation", "urgency", "rationale",
                 "argumentsAgainst", "whatWouldChangeThis"],
}

PROMPT = """A home-monitoring agent has flagged a finding for a patient three days
after a cardiac stent. Decide whether a clinician needs to be paged now.

FINDING: {finding}
REPORTED: {observation}
MATCHED RED FLAGS FROM THEIR DISCHARGE DOCUMENT: {flags}
MONITOR'S REASONING: {reasoning}

Paging has a real cost. A clinician who is woken for findings that did not need
them stops reading the alerts, and then the alerting system has made things
worse than no alerting at all. So do not recommend escalation reflexively.

Equally: a missed cardiac event kills. Under genuine uncertainty, recommend
escalation.

Return:
- recommendEscalation: true if a clinician should be paged now.
- urgency: emergency (minutes) · urgent (this shift) · routine (next working
  day) · none.
- rationale: the single strongest reason for your recommendation.
- argumentsAgainst: the strongest case AGAINST your own recommendation. Always
  fill this in. If you cannot argue the other side, you have not thought about it.
- whatWouldChangeThis: the specific additional fact that would flip your answer.

Judge the finding as reported, and treat unreported information as unknown
rather than reassuring."""

# Symptoms carrying a printed instruction to return to hospital. A model's
# reassurance never overrides these.
#
# Written as the phrases people actually use, not as clinical vocabulary. A
# daughter texting at midnight writes "he passed out", not "syncope", and
# "fainting" does not appear anywhere in "he fainted in the kitchen". The first
# version of this list matched only textbook terms and missed all of that.
#
# Single ambiguous words are deliberately absent. "blood" would fire on "blood
# pressure" and "blood thinner"; "breath" would fire on "breathing fine". A
# check that cries wolf makes restraint impossible, and restraint is the point.
_NEVER_SUPPRESS = (
    "chest pain", "chest pressure", "chest tightness", "tightness in his chest",
    "tightness in her chest", "tightness in my chest", "pain in his chest",
    "pain in her chest", "pain in my chest", "heavy feeling in his chest",
    "heavy feeling in her chest", "heavy feeling in my chest", "chest heaviness",
    "short of breath", "shortness of breath", "breathless", "can't breathe",
    "cannot breathe", "trouble breathing", "difficulty breathing",
    "struggling to breathe",
    "bleeding", "bled", "blood loss",
    "faint", "fainted", "fainting", "passed out", "blacked out",
    "collapse", "collapsed", "syncope", "unresponsive",
)

# Cues that turn a symptom mention into its own denial. Home reports are full of
# these — "no chest pain, no dizziness" is how a careful family member rules
# things out, and a matcher that reads that as a positive finding would escalate
# every reassuring message it received.
_NEGATIONS = ("no ", "not ", "n't ", "never ", "without ", "denies ", "denied ",
              "free of ", "negative for ", "any ")

_WINDOW = 24        # characters before a match searched for a negation cue


def _negated(text: str, at: int) -> bool:
    """Is the match at ``at`` inside a denial?

    A deliberately small NegEx: look back a short span and stop at a clause
    boundary, so "no chest pain, but she is bleeding" negates the first and not
    the second. Sentence-level scanning gets that wrong, which is the expensive
    direction of wrong.
    """
    before = text[max(0, at - _WINDOW):at]
    for cut in (",", ";", ".", " but ", " and "):
        idx = before.rfind(cut)
        if idx != -1:
            before = before[idx + len(cut):]
    return any(cue in before for cue in _NEGATIONS)


def _hard_override(matched: list[str], observation: str) -> str | None:
    """Deterministic floor under the model's judgement.

    Returns the reason to force escalation, or None. Keyword-based and dull on
    purpose: this is the check that has to keep working on a day when the model
    is not itself, so it must not depend on a model to run.
    """
    for flag in matched:
        low = flag.lower()
        if any(term in low for term in _NEVER_SUPPRESS):
            return f"'{flag}' is on this patient's printed return-to-emergency list"

    low_obs = observation.lower()
    for term in _NEVER_SUPPRESS:
        start = low_obs.find(term)
        while start != -1:
            if not _negated(low_obs, start):
                return (f"the report mentions '{term}', "
                        "a documented return-to-emergency symptom")
            start = low_obs.find(term, start + 1)
    return None


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    inp = task.get("input") or {}
    finding = (inp.get("finding") or inp.get("observation") or "").strip()
    if not finding:
        raise Refusal("nothing to assess", options=["Send a finding from the Watchman"])

    observation = inp.get("observation") or finding
    matched = inp.get("matchedFlags") or []

    # ---- step 1: assess (the model advises) --------------------------------
    def _assess(_key: str) -> dict[str, Any]:
        out, meta = gemini.generate_json(
            PROMPT.format(
                finding=finding, observation=observation,
                flags=", ".join(matched) or "none",
                reasoning=inp.get("reasoning") or "—",
            ),
            SCHEMA,
            model=settings.model_reason,
        )
        return {**out, "model": meta["model"], "latencyMs": meta["latencyMs"]}

    a = ledger.run_step(pid, task_id, "escalator", "assess", _assess)

    # ---- step 2: decide (the code decides) ---------------------------------
    override = _hard_override(matched, observation)
    escalating = bool(a.get("recommendEscalation")) or override is not None

    if not escalating:
        # Stand down — but leave the full reasoning behind, including what would
        # have changed the answer. A decision not to act has to be as auditable
        # as a decision to act, or nobody can review it later.
        def _stand_down(_key: str) -> dict[str, Any]:
            return {"decision": "no human needed", "urgency": a.get("urgency"),
                    "rationale": a.get("rationale"),
                    "argumentsAgainst": a.get("argumentsAgainst"),
                    "whatWouldChangeThis": a.get("whatWouldChangeThis"),
                    "model": a.get("model")}

        d = ledger.run_step(pid, task_id, "escalator", "stand_down", _stand_down)
        ledger.audit(pid, "action", "escalator",
                     f"stood down — no clinician paged: {d['rationale']}", task_id,
                     {"standDown": True, "whatWouldChangeThis": d["whatWouldChangeThis"]})
        return f"no human needed — {d['rationale']}"

    # ---- escalate ----------------------------------------------------------
    # Only call it an override when the model actually said otherwise. Logging a
    # disagreement that did not happen inflates how often the safety net catches
    # something, and the whole value of this trail is that it can be trusted
    # when someone reads it back.
    model_disagreed = override is not None and not a.get("recommendEscalation")
    if model_disagreed:
        ledger.audit(pid, "action", "escalator",
                     f"model recommendation overridden — {override}", task_id,
                     {"hardOverride": True, "modelSaid": False})
    elif override is not None:
        ledger.audit(pid, "action", "escalator",
                     f"escalating — model and red-flag rule agree ({override})", task_id,
                     {"hardOverride": False, "redFlagRuleAgrees": True})

    urgency = "emergency" if override else (a.get("urgency") or "urgent")
    raise Escalation(
        f"{finding} — {urgency}",
        {
            "urgency": urgency,
            "matchedFlags": matched,
            "rationale": override or a.get("rationale"),
            "argumentsAgainst": a.get("argumentsAgainst"),
            "hardOverride": model_disagreed,
            "slaMinutes": settings.sla_minutes.get(urgency, 60),
            "observation": observation,
            "model": a.get("model"),
        },
    )
