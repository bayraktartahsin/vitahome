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

from ..config import settings
from ..fleet import ledger
from ..fleet.runtime import Refusal
from ..integrations import fhir

log = logging.getLogger("vitahome.scheduler")

# A tiny directory stands in for a real provider network. Declared, not hidden:
# the console labels this "provider directory (demo)".
# specialty -> (who you are seeing, where, what to call the appointment)
#
# The clinician and the specialty are separate fields on purpose. They used to
# be one string ("Dr. Chen · Cardiology"), which meant every calendar entry the
# family saw read "Cardiology — Dr. Chen · Cardiology". A title on somebody's
# phone is a piece of design, not a log line.
_DIRECTORY = {
    "cardiology":    ("Dr. Chen",            "Mercy General · Heart Center",
                      "Cardiology follow-up"),
    "primary care":  ("Dr. Alvarez",         "Mercy General · Family Medicine",
                      "Primary care follow-up"),
    "cardiac rehab": ("the rehab team",      "Mercy General · Rehabilitation",
                      "Cardiac rehab intake"),
}


def _slot(days_out: int) -> datetime:
    """Next weekday at 10:00 local, days_out from now."""
    d = datetime.now(timezone.utc) + timedelta(days=days_out)
    while d.weekday() >= 5:                    # push weekends to Monday
        d += timedelta(days=1)
    return d.replace(hour=10, minute=0, second=0, microsecond=0)


def _patient_fhir_id(pid: str, inp: dict[str, Any]) -> str | None:
    """Resolve the FHIR Patient id ourselves.

    Pub/Sub messages carry references, never PHI — so the agent looks the
    patient up inside its own IAM scope rather than trusting the payload.
    """
    if inp.get("fhirPatientId"):
        return inp["fhirPatientId"]
    snap = ledger.db().collection("patients").document(pid).get()
    return ((snap.to_dict() or {}).get("profile") or {}).get("fhirPatientId")


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    inp = task.get("input") or {}
    specialty = (inp.get("specialty") or "").strip().lower()
    days_out = int(inp.get("daysOut") or 7)
    instruction_id = task.get("instructionId")
    fhir_patient = _patient_fhir_id(pid, inp)
    if not fhir_patient:
        raise Refusal(
            "no FHIR patient record is linked to this fleet",
            options=["Link the patient record", "Seed the demo patient"],
        )

    if specialty not in _DIRECTORY:
        # We do not guess which clinician the patient should see.
        raise Refusal(
            f"'{specialty or 'unspecified'}' does not match a known specialty",
            options=[f"Book with {v[0]}" for v in _DIRECTORY.values()] + ["Clarify with the discharging team"],
        )

    # ---- step 1: which provider -------------------------------------------
    def _resolve(_key: str) -> dict[str, Any]:
        practitioner, location, title = _DIRECTORY[specialty]
        return {"practitioner": practitioner, "location": location,
                "title": title,
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
                {"actor": {"reference": f"Patient/{fhir_patient}"}, "status": "accepted"},
            ],
        }, idem=key)
        return {"fhirId": res.get("id"), "start": start.isoformat(),
                "practitioner": provider["practitioner"],
                "externalRef": f"Appointment/{res.get('id')}",
                "system": "Google Cloud Healthcare API (FHIR R4)"}

    appt = ledger.run_step(pid, task_id, "scheduler", "fhir_appointment", _appointment)
    ledger.bump_ledger(pid, "systemsTouched")

    # A replayed step hands back the result the *previous* attempt stored, so a
    # field added after that attempt began will not be there. The drill replays
    # steps on purpose, and a deploy can land between two attempts of the same
    # task — so every read of a step result carries its own fallback rather than
    # assuming this process wrote it.
    title = provider.get("title") or f"{provider.get('specialty', 'Follow-up').title()} follow-up"
    where_at = provider.get("location") or ""

    # ---- step 2b: the same booking, on a real phone -----------------------
    # A second, independent external system — a Google Calendar the fleet owns,
    # shared to the family's account. Failure here must never fail the booking:
    # the clinical record is the source of truth, the calendar is how humans
    # see it. So unavailability is caught, declared, and moved past — the one
    # place in this agent where an exception is absorbed, and it says so.
    def _calendar(key: str) -> dict[str, Any]:
        if not settings.calendar_enabled:
            return {"simulated": True, "note": "calendar disabled by configuration"}
        # The shared calendar is a real person's phone. The 200-fleet cohort is
        # a load test — writing it there buries the demo patient's three real
        # appointments under hundreds of synthetic ones at the same 10:00 slot,
        # which is exactly what happened. Cohort fleets still book into FHIR;
        # they just do not spam a human's calendar to prove they can.
        if not settings.calendar_writes_for(pid):
            return {"simulated": True,
                    "note": "cohort fleet — booked in FHIR, kept off the shared calendar"}
        try:
            from ..integrations import calendar
            ev = calendar.create_event(
                summary=title,
                location=where_at,
                description=(
                    f"With {provider['practitioner']}.\n\n"
                    f"Booked by VitaHome from the discharge summary"
                    f"{f' (instruction {instruction_id})' if instruction_id else ''}.\n"
                    f"Clinical record: {appt.get('externalRef')}\n\n"
                    f"Demo booking — the patient record is synthetic."
                ),
                start_iso=start.isoformat().replace("+00:00", "Z"),
                end_iso=end.isoformat().replace("+00:00", "Z"),
                idem=key,
                patient_id=pid,
            )
            return {**ev, "externalRef": f"gcal:{ev['eventId']}"}
        except calendar.CalendarUnavailable as e:
            return {"simulated": True,
                    "note": f"calendar unavailable — declared simulation ({e})"}

    cal = ledger.run_step(pid, task_id, "scheduler", "calendar_event", _calendar)
    if not cal.get("simulated"):
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
    where = "FHIR + phone calendar" if not cal.get("simulated") else "FHIR"
    return f"booked {title} with {provider['practitioner']}, {when} ({where})"
