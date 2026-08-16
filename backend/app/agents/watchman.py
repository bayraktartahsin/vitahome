"""👁 Watchman — monitors for the red flags written on THIS document.

Not a generic vitals alarm. When the Parser reads a discharge summary it lifts
out that document's own "return to emergency if…" list, and the Watchman arms
itself against exactly those symptoms. A cardiac discharge and a post-partum
discharge produce different monitors from the same agent, because the document
supplies the thresholds.

The Watchman does not decide whether to wake a human. It observes, records to
the clinical store, and hands the finding to the Escalator. Keeping observation
separate from escalation is deliberate: the component that notices things should
not also be the component that judges them, or "notice more" and "page more"
become the same dial.

Steps:
  1. record_observation   write a real FHIR Observation
  2. match_flags          compare against this document's red flags
  → dispatch to the Escalator when something matches or looks off
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..fleet import dispatch, ledger
from ..fleet.runtime import Refusal
from ..integrations import fhir, gemini

log = logging.getLogger("vitahome.watchman")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "matchedFlags": {"type": "array", "items": {"type": "string"}},
        "concerning": {"type": "boolean"},
        "finding": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["matchedFlags", "concerning", "finding", "reasoning"],
}

PROMPT = """A patient recovering at home after a cardiac stent has reported the
following. Decide whether it corresponds to anything on their discharge
document's return-to-emergency list.

REPORTED:
{observation}

THIS DOCUMENT'S RETURN-TO-EMERGENCY LIST:
{flags}

CONTEXT FROM THE DISCHARGE:
{context}

Return:
- matchedFlags: which items from the list this report corresponds to. Use the
  exact wording from the list. Empty if none.
- concerning: true if a clinician should SEE this at some point, even when it
  matches nothing on the list. This is a deliberately low bar. It does not mean
  "wake someone up" — a separate agent makes that decision and holds the high
  bar. Set it true for anything new, unexplained, or that a careful family
  member thought worth reporting. Set it false only for the clearly benign:
  expected medication effects the patient has already been told about, and
  routine progress.
  The printed red-flag list is not exhaustive, and treating it as exhaustive is
  how you miss the symptom nobody thought to print.
- finding: one clinical sentence describing what was reported.
- reasoning: why you reached that conclusion, including anything that argues
  against concern (exertion, a known medication effect, prompt resolution).

Judge the report as written. Do not assume unreported symptoms are absent OR
present — say what is unknown in the reasoning if it matters."""


def _now_iso() -> str:
    """FHIR instant format — 'Z', not '+00:00'."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _care_plan(pid: str) -> tuple[str | None, dict[str, Any]]:
    snap = ledger.db().collection("patients").document(pid).get()
    doc = snap.to_dict() or {}
    return (doc.get("profile") or {}).get("fhirPatientId"), (doc.get("carePlan") or {})


def _red_flags(plan: dict[str, Any]) -> list[str]:
    """The flags this specific document asked us to watch for."""
    flags: list[str] = []
    for ins in plan.get("instructions", []):
        if ins.get("type") == "red_flag":
            flags.extend(ins.get("flags") or [])
            if not ins.get("flags") and ins.get("text"):
                flags.append(ins["text"])
    return flags


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    inp = task.get("input") or {}
    observation = (inp.get("observation") or "").strip()
    if not observation:
        raise Refusal("no observation to evaluate",
                      options=["Send a vitals reading", "Send a symptom report"])

    fhir_patient, plan = _care_plan(pid)
    if not fhir_patient:
        raise Refusal("no FHIR patient record is linked to this fleet",
                      options=["Link the patient record", "Seed the demo patient"])

    flags = _red_flags(plan)
    if not flags:
        raise Refusal(
            "this care plan has no return-to-emergency list to monitor against",
            options=["Re-parse the discharge document", "Add red flags manually"],
        )

    # ---- step 1: it goes in the record whether or not it is alarming --------
    # Recording first matters: if this agent dies during evaluation, the
    # observation is already durable and the replay does not lose it.
    def _record(key: str) -> dict[str, Any]:
        res = fhir.create("Observation", {
            "status": "final",
            "category": [{"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "survey", "display": "Survey"}]}],
            "code": {"text": "Patient-reported symptom (home monitoring)"},
            "subject": {"reference": f"Patient/{fhir_patient}"},
            # FHIR rejects a null datetime outright, and an omitted one loses
            # when the report arrived — which is the field a clinician reads
            # first. Stamp it here when the caller did not supply one.
            "effectiveDateTime": inp.get("at") or _now_iso(),
            "valueString": observation,
        }, idem=key)
        return {"externalRef": f"Observation/{res.get('id')}",
                "system": "Google Cloud Healthcare API (FHIR R4)"}

    ledger.run_step(pid, task_id, "watchman", "record_observation", _record)
    ledger.bump_ledger(pid, "systemsTouched")

    # ---- step 2: does it match what this document told us to watch for? ----
    def _match(_key: str) -> dict[str, Any]:
        out, meta = gemini.generate_json(
            PROMPT.format(
                observation=observation,
                flags="\n".join(f"  - {f}" for f in flags),
                context=inp.get("context") or "post-PCI, day 3 at home",
            ),
            SCHEMA,
            model=settings.model_reason,
        )
        return {**out, "model": meta["model"], "latencyMs": meta["latencyMs"]}

    assessment = ledger.run_step(pid, task_id, "watchman", "match_flags", _match)
    matched = assessment.get("matchedFlags") or []
    concerning = bool(assessment.get("concerning"))

    if not matched and not concerning:
        return f"observed and recorded — no red flag matched: {assessment['finding']}"

    # Hand it on. The Watchman never pages a human itself.
    esc_task = dispatch.dispatch(pid, "escalator", task.get("instructionId"), {
        "observation": observation,
        "finding": assessment["finding"],
        "matchedFlags": matched,
        "reasoning": assessment.get("reasoning"),
        "sourceTaskId": task_id,
    })
    flag_txt = ", ".join(matched) if matched else "no listed flag, but concerning"
    return f"flag matched ({flag_txt}) — routed to the Escalator as {esc_task}"
