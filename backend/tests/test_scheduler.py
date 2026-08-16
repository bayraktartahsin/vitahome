"""Scheduler behaviour — especially the refusal, which is the product thesis."""
from __future__ import annotations

import pytest

from app.agents import scheduler
from app.fleet.runtime import Refusal


class _FakeDoc:
    """Just enough Firestore for the confirm step, which writes the booked
    status back onto the care plan."""

    def __init__(self, data: dict):
        self.data = data
        self.writes: list[dict] = []

    def collection(self, _name):
        return self

    def document(self, _id):
        return self

    def get(self):
        return self

    def to_dict(self):
        return self.data

    def set(self, payload, merge=False):
        self.writes.append(payload)
        self.data.update(payload)


class _FakeLedger:
    """Records steps and replays them the way the real ledger does, so we can
    assert idempotent behaviour without Firestore."""

    def __init__(self, already_done: dict | None = None, plan: dict | None = None):
        self.calls: list[str] = []
        self.done = already_done or {}
        self.bumps: list[str] = []
        self.doc = _FakeDoc({"carePlan": plan or {
            "instructions": [{"id": "i_06", "type": "followup", "status": "pending"}]
        }})

    def run_step(self, pid, task_id, agent, step_name, fn):
        self.calls.append(step_name)
        if step_name in self.done:
            return self.done[step_name]          # replay: skip the side effect
        return fn(f"{task_id}:{step_name}")

    def bump_ledger(self, pid, field):
        self.bumps.append(field)

    def db(self):
        return self.doc


def _task(specialty: str = "cardiology", days: int = 7) -> dict:
    return {"input": {"specialty": specialty, "daysOut": days,
                      "fhirPatientId": "fake"}, "instructionId": "i_06"}


def test_refuses_unknown_specialty_instead_of_guessing(monkeypatch):
    """Booking the wrong clinician is worse than booking nothing."""
    monkeypatch.setattr(scheduler, "ledger", _FakeLedger())
    with pytest.raises(Refusal) as ex:
        scheduler.body("p_hero", "t_1", _task(specialty="dermatolgy"))   # typo'd
    assert "dermatolgy" in str(ex.value)
    assert ex.value.options, "a refusal must offer the human options"


def test_refuses_when_specialty_missing(monkeypatch):
    monkeypatch.setattr(scheduler, "ledger", _FakeLedger())
    with pytest.raises(Refusal):
        scheduler.body("p_hero", "t_1", _task(specialty=""))


def test_books_known_specialty_through_three_steps(monkeypatch):
    fake = _FakeLedger()
    monkeypatch.setattr(scheduler, "ledger", fake)
    monkeypatch.setattr(scheduler.fhir, "create",
                        lambda rt, body, idem=None: {"id": "appt-123"})

    summary = scheduler.body("p_hero", "t_1", _task())

    assert fake.calls == ["resolve_provider", "fhir_appointment", "confirm"]
    assert "cardiology" in summary
    assert "systemsTouched" in fake.bumps, "a real external system was touched"

    # the care plan must reflect the booking, with a traceable external ref
    booked = fake.doc.data["carePlan"]["instructions"][0]
    assert booked["status"] == "booked"
    assert booked["bookedRef"] == "Appointment/appt-123"


def test_replay_skips_the_fhir_write(monkeypatch):
    """The Failure Drill in miniature: if the appointment step already ran,
    a replay must not call FHIR again."""
    fake = _FakeLedger(already_done={
        "resolve_provider": {"practitioner": "Dr. Chen · Cardiology",
                             "location": "Mercy General", "specialty": "cardiology"},
        "fhir_appointment": {"fhirId": "appt-123", "start": "2026-08-24T10:00:00",
                             "practitioner": "Dr. Chen · Cardiology",
                             "externalRef": "Appointment/appt-123"},
    })
    monkeypatch.setattr(scheduler, "ledger", fake)

    def _explode(*_a, **_k):
        raise AssertionError("FHIR must not be called on replay of a completed step")

    monkeypatch.setattr(scheduler.fhir, "create", _explode)
    summary = scheduler.body("p_hero", "t_1", _task())
    assert "cardiology" in summary


def test_appointment_slot_never_lands_on_a_weekend():
    for days in range(1, 30):
        assert scheduler._slot(days).weekday() < 5
