"""🏥 Pharmacist — turns prescriptions into a clock.

"Ticagrelor 90 mg PO twice daily for 12 months" is not a schedule. It is a
sentence, and somebody at home has to convert it into two specific moments in a
day, alongside four other drugs, some of which want food and one of which wants
to be nowhere near another. That conversion is where doses get missed — not
because anyone misunderstood the medicine, but because nobody ever wrote down
what 8am actually looks like.

So this agent produces the clock. Real times, real days, and the timing
constraints spelled out in plain language.

**It never alters a dose.** It reads what was prescribed and lays it out. If a
dosage line cannot be turned into a schedule with confidence — a range, a
missing frequency, a PRN instruction with no ceiling — it refuses and hands the
question to a pharmacist rather than inventing a plausible time.

Steps, each independently idempotent:

  1. fetch_prescriptions  active MedicationRequests from the FHIR store
  2. build_schedule       free text -> structured times + constraints
  3. write_dispense       a FHIR MedicationDispense per drug
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..config import settings
from ..fleet import ledger
from ..fleet.runtime import Refusal
from ..integrations import fhir, gemini

log = logging.getLogger("vitahome.pharmacist")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "drug": {"type": "string"},
                    "requestId": {"type": "string"},
                    "amount": {"type": "string"},
                    "times": {"type": "array", "items": {"type": "string"}},
                    "withFood": {"type": "boolean"},
                    "note": {"type": "string"},
                    "confident": {"type": "boolean"},
                    "unclear": {"type": "string"},
                },
                "required": ["drug", "amount", "times", "confident"],
            },
        },
        "separations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "drugs": {"type": "array", "items": {"type": "string"}},
                    "hoursApart": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["drugs", "reason"],
            },
        },
    },
    "required": ["doses", "separations"],
}

PROMPT = """Turn these prescriptions into a daily schedule someone can actually follow.

PRESCRIPTIONS:
{meds}

For each drug produce a `doses` entry:
- drug, requestId: copy them exactly as given.
- amount: how much is taken at ONE dose (not the daily total).
- times: specific 24-hour clock times, e.g. ["08:00", "20:00"]. Twice daily
  means roughly twelve hours apart. Once daily at night means bedtime, around
  "22:00". Spread doses realistically around waking hours — nobody takes a pill
  at 03:00 because the arithmetic said so.
- withFood: true only if the medication genuinely requires it.
- note: anything the patient should know about taking this one, in one short
  plain sentence. No jargon.
- confident: false if you cannot turn this line into a schedule without
  guessing — a dose range, a missing frequency, "as needed" with no ceiling, or
  wording you had to interpret. Put what is unclear in `unclear`.
  Be honest here. A guessed schedule is worse than an unanswered question.

Then `separations`: any pair of these drugs that should NOT be taken at the same
time, with how many hours apart and why, in plain language. Only include real,
clinically recognised separations. Do not invent caution.

You are laying out what was prescribed. You never change a dose, add a drug, or
drop one."""


def _active(fhir_patient: str) -> list[dict[str, Any]]:
    out = []
    for mr in fhir.search("MedicationRequest",
                          {"subject": f"Patient/{fhir_patient}", "status": "active",
                           "_count": "50"}):
        out.append({
            "requestId": mr.get("id"),
            "drug": (mr.get("medicationCodeableConcept") or {}).get("text", "?"),
            "dosage": ((mr.get("dosageInstruction") or [{}])[0]).get("text", ""),
        })
    return out


_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    snap = ledger.db().collection("patients").document(pid).get()
    doc = snap.to_dict() or {}
    fhir_patient = (doc.get("profile") or {}).get("fhirPatientId")
    if not fhir_patient:
        raise Refusal("no FHIR patient record is linked to this fleet",
                      options=["Link the patient record", "Seed the demo patient"])

    # ---- step 1: what is actually prescribed right now ---------------------
    def _fetch(_key: str) -> dict[str, Any]:
        meds = _active(fhir_patient)
        return {"medications": meds, "count": len(meds),
                "system": "Google Cloud Healthcare API (FHIR R4)"}

    current = ledger.run_step(pid, task_id, "pharmacist", "fetch_prescriptions", _fetch)
    if not current["medications"]:
        raise Refusal("no active prescriptions to schedule",
                      options=["Run medication reconciliation first"])
    ledger.bump_ledger(pid, "systemsTouched")

    # ---- step 2: the clock -------------------------------------------------
    def _schedule(_key: str) -> dict[str, Any]:
        out, meta = gemini.generate_json(
            PROMPT.format(meds="\n".join(
                f"  - id={m['requestId']} · {m['drug']} · {m['dosage'] or '(no dosage text)'}"
                for m in current["medications"])),
            SCHEMA, model=settings.model_fast,
        )
        return {**out, "model": meta["model"], "latencyMs": meta["latencyMs"]}

    plan = ledger.run_step(pid, task_id, "pharmacist", "build_schedule", _schedule)
    doses = plan.get("doses") or []

    # A malformed clock time is a defect, not a nuance — it would render as a
    # broken schedule in the family view. Treat it exactly like the model
    # telling us it was unsure.
    for d in doses:
        bad = [t for t in (d.get("times") or []) if not _TIME.match(str(t))]
        if bad or not d.get("times"):
            d["confident"] = False
            d["unclear"] = d.get("unclear") or f"could not produce valid times ({bad or 'none given'})"

    unclear = [d for d in doses if not d.get("confident")]
    clear = [d for d in doses if d.get("confident")]

    # ---- step 3: record what is being dispensed ----------------------------
    def _dispense(key: str) -> dict[str, Any]:
        written = []
        for d in clear:
            res = fhir.create("MedicationDispense", {
                "status": "preparation",
                "subject": {"reference": f"Patient/{fhir_patient}"},
                "medicationCodeableConcept": {"text": d["drug"]},
                "dosageInstruction": [{
                    "text": f"{d['amount']} at {', '.join(d['times'])}"
                            + (" with food" if d.get("withFood") else ""),
                }],
            }, idem=f"{key}:{d['drug'].lower().replace(' ', '-')}")
            written.append({"drug": d["drug"], "ref": f"MedicationDispense/{res.get('id')}"})
        return {"dispensed": written, "count": len(written)}

    ledger.run_step(pid, task_id, "pharmacist", "write_dispense", _dispense)

    # The family view reads this. Written before any refusal, so the doses we
    # ARE sure about reach the patient even when one line needs a pharmacist.
    ledger.db().collection("patients").document(pid).set({
        "doseSchedule": {
            "doses": clear,
            "separations": plan.get("separations") or [],
            "unresolved": unclear,
            "builtBy": plan.get("model"),
        },
    }, merge=True)

    if unclear:
        d = unclear[0]
        raise Refusal(
            f"{d['drug']} — cannot be scheduled without guessing: {d.get('unclear', 'dosage unclear')}",
            options=[
                f"Confirm the intended schedule for {d['drug']}",
                "Ask the prescribing clinician to clarify the dosage",
            ],
        )

    n, s = len(clear), len(plan.get("separations") or [])
    return (f"scheduled {n} medication{'s' if n != 1 else ''}"
            + (f", {s} timing separation{'s' if s != 1 else ''} flagged" if s else ""))
