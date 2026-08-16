"""🗣 Coach — one question a day, and it has to be the right one.

Every check-in product asks "how are you feeling today?". That question is
worthless: it has no wrong answer, so it produces no information, and after
four days people stop reading it.

This agent asks exactly one question, chosen from what the fleet actually does
not know right now. On day three after a stent, with an unresolved question
about a blood pressure medication sitting in the clinician's queue, the useful
question is not how he is feeling. It is whether he has been getting dizzy when
he stands up.

The question is selected from live state — the critical instructions, what is
still unbooked, what a human was asked to decide and has not, and what was
reported in the last few days. If everything is quiet, it says so and asks
nothing. A check-in with nothing to learn should not be sent.

Answers do not come back here. They go to the Watchman, which is the component
that knows this document's red flags. The Coach asks; it does not judge.

Steps:
  1. choose_question   pick the single highest-value thing to ask today
  2. record_checkin    write it to FHIR so the asking is part of the record
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..fleet import ledger
from ..fleet.runtime import Refusal
from ..integrations import fhir, gemini

log = logging.getLogger("vitahome.coach")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "worthAsking": {"type": "boolean"},
        "question": {"type": "string"},
        "why": {"type": "string"},
        "about": {"type": "string"},
        "listenFor": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["worthAsking", "question", "why", "about", "listenFor"],
}

PROMPT = """You check in once a day with someone recovering at home. You get ONE
question. Choose it from what is genuinely unknown right now.

DAY {day} AFTER DISCHARGE.

INSTRUCTIONS THAT MATTER MOST:
{critical}

STILL WAITING ON A HUMAN:
{pending}

ALREADY REPORTED IN THE LAST FEW DAYS:
{recent}

ALREADY ASKED (do not repeat these):
{asked}

Pick the question whose answer would change what the fleet does next. Good
questions are specific enough to have a wrong answer. "How are you feeling?"
has no wrong answer and teaches nothing — never ask it.

If there is an unresolved clinical question in the queue, ask about the symptom
that would tell a clinician which way to resolve it. That is usually the highest
value question available.

Return:
- worthAsking: false if there is genuinely nothing useful to learn today. Say so
  rather than manufacturing a question; an unnecessary check-in is how people
  learn to ignore the necessary one.
- question: what you would say. One sentence, warm, plain, no jargon. Address
  them directly. Do not stack two questions into one.
- why: one sentence on what this answer would change. For the record, not for
  the patient.
- about: a short slug for what it concerns, e.g. "dizziness", "ticagrelor-
  adherence", "wound-site".
- listenFor: the specific answers that would need the fleet to act.

Never give medical advice, never reassure, never interpret. You ask."""


def _recent_reports(pid: str, limit: int = 8) -> list[str]:
    from google.cloud import firestore as fs
    rows = (ledger.db().collection("patients").document(pid).collection("audit")
            .order_by("at", direction=fs.Query.DESCENDING).limit(80).stream())
    out = []
    for r in rows:
        d = r.to_dict() or {}
        if d.get("actor") == "watchman" and "observed" in (d.get("detail") or ""):
            out.append(d["detail"])
        if len(out) >= limit:
            break
    return out


def _asked_before(plan: dict[str, Any]) -> list[str]:
    return [c.get("about", "") for c in (plan.get("checkIns") or [])][-10:]


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    snap = ledger.db().collection("patients").document(pid).get()
    doc = snap.to_dict() or {}
    fhir_patient = (doc.get("profile") or {}).get("fhirPatientId")
    plan = doc.get("carePlan") or {}
    if not fhir_patient or not plan.get("instructions"):
        raise Refusal("no care plan to check in against",
                      options=["Parse a discharge document first"])

    critical = [i for i in plan["instructions"] if i.get("criticality") == "CRITICAL"]
    conflicts = doc.get("openConflicts") or []
    day = int((task.get("input") or {}).get("day") or 3)

    # ---- step 1: what is worth asking today --------------------------------
    def _choose(_key: str) -> dict[str, Any]:
        out, meta = gemini.generate_json(
            PROMPT.format(
                day=day,
                critical="\n".join(f"  - {i['text']}" for i in critical) or "  (none)",
                pending="\n".join(f"  - {c.get('drug')}: {c.get('question')}"
                                  for c in conflicts) or "  (nothing)",
                recent="\n".join(f"  - {r}" for r in _recent_reports(pid)) or "  (nothing)",
                asked=", ".join(a for a in _asked_before(plan) if a) or "(nothing yet)",
            ),
            SCHEMA, model=settings.model_reason,
        )
        return {**out, "model": meta["model"], "latencyMs": meta["latencyMs"]}

    q = ledger.run_step(pid, task_id, "coach", "choose_question", _choose)

    if not q.get("worthAsking"):
        ledger.audit(pid, "action", "coach",
                     f"no check-in sent today — {q.get('why', 'nothing new to learn')}",
                     task_id, {"skipped": True})
        return f"no check-in today — {q.get('why', 'nothing worth asking')}"

    # ---- step 2: the asking is part of the record --------------------------
    def _record(key: str) -> dict[str, Any]:
        res = fhir.create("Observation", {
            "status": "registered",
            "category": [{"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "survey", "display": "Survey"}]}],
            "code": {"text": f"Daily check-in — {q['about']}"},
            "subject": {"reference": f"Patient/{fhir_patient}"},
            "effectiveDateTime": datetime.now(timezone.utc)
                .isoformat(timespec="seconds").replace("+00:00", "Z"),
            "valueString": q["question"],
        }, idem=key)
        return {"externalRef": f"Observation/{res.get('id')}"}

    rec = ledger.run_step(pid, task_id, "coach", "record_checkin", _record)

    ledger.db().collection("patients").document(pid).set({
        "openCheckIn": {
            "taskId": task_id, "question": q["question"], "about": q["about"],
            "why": q["why"], "listenFor": q.get("listenFor") or [],
            "askedAt": datetime.now(timezone.utc), "ref": rec.get("externalRef"),
            "answer": None,
        },
        "carePlan": {**plan, "checkIns": [*(plan.get("checkIns") or []),
                                          {"about": q["about"], "at": datetime.now(timezone.utc)}]},
    }, merge=True)

    return f"asked about {q['about']}: “{q['question']}”"
