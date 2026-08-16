"""Pharmacist — lays out what was prescribed, and never invents a time.

A guessed schedule is worse than an unanswered question: it looks authoritative,
it goes on the family's fridge, and nobody knows which line was a guess. So the
interesting behaviour here is what happens to the doses the model was NOT sure
about, and to clock times that came back malformed.
"""
from __future__ import annotations

import pytest

from app.agents import pharmacist
from app.fleet.runtime import Refusal


class _Doc:
    exists = True

    def __init__(self, data):
        self.data, self.merged = data, {}

    def to_dict(self):
        return self.data

    def get(self):
        return self

    def set(self, data, merge=False):
        self.merged.update(data)

    def collection(self, _n):
        return self

    def document(self, _i):
        return self

    def add(self, _d):
        pass


PLAN = {"profile": {"fhirPatientId": "pat-1"}}

ACTIVE = [
    {"requestId": "mr-tica", "drug": "Ticagrelor 90 mg", "dosage": "90 mg PO twice daily"},
    {"requestId": "mr-asa", "drug": "Aspirin 81 mg", "dosage": "81 mg PO daily"},
]


def _dose(drug="Ticagrelor 90 mg", times=("08:00", "20:00"), confident=True, **kw):
    return {"drug": drug, "requestId": "mr-x", "amount": "1 tablet",
            "times": list(times), "confident": confident, **kw}


@pytest.fixture
def run(monkeypatch):
    def _go(doses, separations=(), active=ACTIVE, plan=PLAN):
        doc = _Doc(dict(plan))
        written: list[str] = []
        monkeypatch.setattr(pharmacist.ledger, "db", lambda: doc)
        monkeypatch.setattr(pharmacist.ledger, "bump_ledger", lambda *a, **k: None)
        monkeypatch.setattr(pharmacist.ledger, "audit", lambda *a, **k: None)
        monkeypatch.setattr(pharmacist.ledger, "run_step",
                            lambda pid, tid, ag, name, fn: fn(f"{tid}:{name}"))
        monkeypatch.setattr(pharmacist, "_active", lambda _p: active)
        monkeypatch.setattr(pharmacist.fhir, "create",
                            lambda rt, b, idem=None: written.append(
                                b["medicationCodeableConcept"]["text"]) or {"id": "d1"})
        monkeypatch.setattr(
            pharmacist.gemini, "generate_json",
            lambda *a, **k: ({"doses": doses, "separations": list(separations)},
                             {"model": "gemini-3.5-flash-lite", "latencyMs": 900}),
        )
        return doc, written

    return _go


# ------------------------------------------------------------- happy path

def test_a_clear_schedule_is_written_and_dispensed(run):
    doc, written = run([_dose(), _dose("Aspirin 81 mg", ("08:00",))])
    summary = pharmacist.body("p", "t", {})
    assert "scheduled 2 medications" in summary
    assert written == ["Ticagrelor 90 mg", "Aspirin 81 mg"]
    assert len(doc.merged["doseSchedule"]["doses"]) == 2


def test_timing_separations_are_reported(run):
    run([_dose()], separations=[{"drugs": ["A", "B"], "hoursApart": 2,
                                "reason": "one blocks absorption of the other"}])
    assert "1 timing separation flagged" in pharmacist.body("p", "t", {})


# ------------------------------------------------- refuses rather than guesses

def test_an_unsure_dose_refuses_instead_of_inventing_a_time(run):
    run([_dose("Warfarin", confident=False, unclear="dose range, no frequency")])
    with pytest.raises(Refusal) as e:
        pharmacist.body("p", "t", {})
    assert "Warfarin" in e.value.reason and "dose range" in e.value.reason


def test_malformed_clock_times_are_treated_as_unsure(run):
    """A model can be confident and still emit "morning" or "8pm". That renders
    as a broken schedule on the family's screen, so it is downgraded to the same
    path as an admitted guess."""
    run([_dose(times=("morning", "8pm"))])
    with pytest.raises(Refusal) as e:
        pharmacist.body("p", "t", {})
    assert "could not produce valid times" in e.value.reason


def test_an_empty_time_list_is_not_a_valid_schedule(run):
    run([_dose(times=())])
    with pytest.raises(Refusal):
        pharmacist.body("p", "t", {})


@pytest.mark.parametrize("t", ["24:00", "8:00", "0800", "08:60", ""])
def test_invalid_times_are_rejected(run, t):
    run([_dose(times=(t,))])
    with pytest.raises(Refusal):
        pharmacist.body("p", "t", {})


def test_the_confident_doses_still_reach_the_patient(run):
    """One unschedulable line must not withhold four that are fine. Safety that
    blocks everything gets switched off."""
    doc, written = run([
        _dose("Ticagrelor 90 mg"),
        _dose("Aspirin 81 mg", ("08:00",)),
        _dose("Warfarin", confident=False, unclear="no frequency given"),
    ])
    with pytest.raises(Refusal):
        pharmacist.body("p", "t", {})
    assert written == ["Ticagrelor 90 mg", "Aspirin 81 mg"]
    sched = doc.merged["doseSchedule"]
    assert len(sched["doses"]) == 2 and len(sched["unresolved"]) == 1


# ------------------------------------------------------------------ guards

def test_no_prescriptions_refuses_rather_than_reporting_an_empty_success(run):
    run([], active=[])
    with pytest.raises(Refusal) as e:
        pharmacist.body("p", "t", {})
    assert "no active prescriptions" in e.value.reason


def test_missing_patient_record_refuses(run):
    run([_dose()], plan={"profile": {}})
    with pytest.raises(Refusal) as e:
        pharmacist.body("p", "t", {})
    assert "FHIR patient record" in e.value.reason
