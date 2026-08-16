"""📅 Scheduler — books every follow-up the document requires.

Three steps, each independently idempotent:

  1. resolve_provider   pick the clinic/specialty for this instruction
  2. fhir_appointment   write a real FHIR Appointment to Cloud Healthcare API
  3. confirm            mark the instruction booked on the care plan

Every step carries a deterministic idempotency key. Kill this agent between any
two steps and the replay skips what already happened. The FHIR write is
additionally guarded by search-before-create on that same key, so even a crash
in the window between "resource created" and "step recorded" cannot double-book.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..fleet import ledger
from ..fleet.runtime import Refusal
from ..integrations import fhir

log = logging.getLogger("vitahome.scheduler")

# A tiny directory stands in for a real provider network. Declared, not hidden:
# the console labels this "provider directory (demo)".
_DIRECTORY = {
    "cardiology":   ("Dr. Chen · Cardiology",       "Mercy General · Heart Center"),
    "primary care": ("Dr. Alvarez · Primary Care",  "Mercy General · Family Medicine"),
    "cardiac rehab": ("Cardiac Rehab Intake",       "Mercy General · Rehabilitation"),
}


def _slot(days_out: int) -> datetime:
    """Next weekday at 10:00 local, days_out from now."""
    d = datetime.now(timezone.utc) + timedelta(days=days_out)
    while d.weekday() >= 5:                    # push weekends to Monday
        d += timedelta(days=1)
    return d.replace(hour=10, minute=0, second=0, microsecond=0)


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    inp = task.get("input") or {}
    specialty = (inp.get("specialty") or "").strip().lower()
    days_out = int(inp.get("daysOut") or 7)
    instruction_id = task.get("instructionId")

    if specialty not in _DIRECTORY:
        # We do not guess which clinician the patient should see.
        raise Refusal(
            f"'{specialty or 'unspecified'}' does not match a known specialty",
            options=[f"Book with {v[0]}" for v in _DIRECTORY.values()] + ["Clarify with the discharging team"],
        )

    # ---- step 1: which provider -------------------------------------------
    def _resolve(_key: str) -> dict[str, Any]:
        practitioner, location = _DIRECTORY[specialty]
        return {"practitioner": practitioner, "location": location,
                "specialty": specialty, "source": "provider directory (demo)"}

    provider = ledger.run_step(pid, task_id, "scheduler", "resolve_provider", _resolve)

    # ---- step 2: real FHIR Appointment ------------------------------------
    start = _slot(days_out)
    end = start + timedelta(minutes=30)

    def _appointment(key: str) -> dict[str, Any]:
        res = fhir.create("Appointment", {
            "status": "booked",
            "description": f"{provider['specialty'].title()} follow-up — booked by VitaHome",
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "minutesDuration": 30,
            "comment": f"Auto-booked from discharge instruction {instruction_id or '—'}",
            "participant": [
                {"actor": {"display": provider["practitioner"]}, "status": "accepted"},
                {"actor": {"reference": f"Patient/{inp.get('fhirPatientId', 'unknown')}"},
                 "status": "accepted"},
            ],
        }, idem=key)
        return {"fhirId": res.get("id"), "start": start.isoformat(),
                "practitioner": provider["practitioner"],
                "externalRef": f"Appointment/{res.get('id')}",
                "system": "Google Cloud Healthcare API (FHIR R4)"}

    appt = ledger.run_step(pid, task_id, "scheduler", "fhir_appointment", _appointment)
    ledger.bump_ledger(pid, "systemsTouched")

    # ---- step 3: reflect it on the care plan ------------------------------
    def _confirm(_key: str) -> dict[str, Any]:
        if instruction_id:
            ref = ledger.db().collection("patients").document(pid)
            snap = ref.get()
            plan = (snap.to_dict() or {}).get("carePlan") or {}
            for ins in plan.get("instructions", []):
                if ins.get("id") == instruction_id:
                    ins["status"] = "booked"
                    ins["bookedRef"] = appt.get("externalRef")
            ref.set({"carePlan": plan}, merge=True)
        return {"instructionId": instruction_id, "status": "booked"}

    ledger.run_step(pid, task_id, "scheduler", "confirm", _confirm)

    when = start.strftime("%a %d %b, %H:%M")
    return f"booked {provider['specialty']} — {provider['practitioner']}, {when}"
