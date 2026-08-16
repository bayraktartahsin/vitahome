"""Watchman — record first, judge second, and never page anyone itself.

The FHIR shape assertions here are not ceremony. The first live run of this
agent failed five times and dead-lettered because effectiveDateTime was null,
which the Healthcare API rejects outright. That is a one-line bug that costs a
whole demo take, and it is exactly the kind of thing a unit test catches for
free.
"""
from __future__ import annotations

import pytest

from app.agents import watchman
from app.fleet.runtime import Refusal


PLAN = {
    "profile": {"fhirPatientId": "pat-1"},
    "carePlan": {"instructions": [
        {"id": "i_12", "type": "red_flag",
         "text": "Return to emergency if: chest pain, bleeding",
         "flags": ["chest pain", "shortness of breath at rest", "bleeding", "fainting"]},
        {"id": "i_02", "type": "medication", "text": "Ticagrelor"},
    ]},
}


@pytest.fixture
def run(monkeypatch):
    def _go(matched: list[str], concerning: bool, plan=PLAN):
        created: list[dict] = []
        dispatched: list[tuple] = []

        class _Doc:
            exists = True
            def to_dict(self): return plan
            def get(self): return self
            def collection(self, _n): return self
            def document(self, _i): return self
            def add(self, _d): pass
            def set(self, _d, merge=False): pass

        monkeypatch.setattr(watchman.ledger, "db", lambda: _Doc())
        monkeypatch.setattr(watchman.ledger, "bump_ledger", lambda *a, **k: None)
        monkeypatch.setattr(watchman.ledger, "audit", lambda *a, **k: None)
        monkeypatch.setattr(watchman.ledger, "run_step",
                            lambda pid, tid, ag, name, fn: fn(f"{tid}:{name}"))
        monkeypatch.setattr(watchman.fhir, "create",
                            lambda rt, b, idem=None: created.append({**b, "_type": rt})
                            or {"id": "obs-1"})
        monkeypatch.setattr(watchman.dispatch, "dispatch",
                            lambda pid, agent, iid, payload: dispatched.append(
                                (agent, payload)) or "t_esc")
        monkeypatch.setattr(
            watchman.gemini, "generate_json",
            lambda *a, **k: ({"matchedFlags": matched, "concerning": concerning,
                              "finding": "a finding", "reasoning": "because"},
                             {"model": "gemini-3.7-flash", "latencyMs": 1900}),
        )
        return created, dispatched

    return _go


def _task(**inp):
    return {"input": {"observation": "he says his chest feels heavy", **inp}}


# ------------------------------------------------------------- FHIR contract

def test_the_observation_carries_a_real_timestamp(run):
    """The regression. A null effectiveDateTime is a FHIR 400, and the retry
    loop then burns five attempts before dead-lettering."""
    created, _ = run(matched=[], concerning=False)
    watchman.body("p", "t", _task())
    obs = created[0]
    assert obs["effectiveDateTime"], "effectiveDateTime must never be null"
    assert obs["effectiveDateTime"].endswith("Z"), "FHIR instants use Z, not +00:00"


def test_a_supplied_timestamp_is_preserved(run):
    created, _ = run(matched=[], concerning=False)
    watchman.body("p", "t", _task(at="2026-08-16T09:30:00Z"))
    assert created[0]["effectiveDateTime"] == "2026-08-16T09:30:00Z"


def test_the_observation_is_recorded_before_it_is_judged(run):
    """Recording first means a crash during evaluation cannot lose the report."""
    created, _ = run(matched=[], concerning=False)
    watchman.body("p", "t", _task())
    assert created and created[0]["_type"] == "Observation"
    assert created[0]["subject"]["reference"] == "Patient/pat-1"


def test_benign_observations_are_still_written_to_the_record(run):
    """Only alarming things reaching the chart is how a record becomes useless."""
    created, dispatched = run(matched=[], concerning=False)
    watchman.body("p", "t", _task(observation="slept well, walked to the postbox"))
    assert len(created) == 1
    assert dispatched == []


# --------------------------------------------------------------- separation

def test_a_matched_flag_is_handed_to_the_escalator_not_escalated_here(run):
    """The Watchman observes. It never decides that a human is needed — if it
    did, 'notice more' and 'page more' would become the same dial."""
    _, dispatched = run(matched=["chest pain"], concerning=True)
    summary = watchman.body("p", "t", _task())
    assert dispatched and dispatched[0][0] == "escalator"
    assert dispatched[0][1]["matchedFlags"] == ["chest pain"]
    assert "Escalator" in summary


def test_concerning_but_unlisted_findings_still_route_onward(run):
    """The printed red-flag list is not exhaustive, and treating it as exhaustive
    is how you miss the symptom nobody thought to print."""
    _, dispatched = run(matched=[], concerning=True)
    watchman.body("p", "t", _task(observation="confused and slurring words"))
    assert dispatched, "a concerning finding was dropped because it matched no list"


def test_the_monitor_reasoning_travels_with_the_handoff(run):
    _, dispatched = run(matched=["bleeding"], concerning=True)
    watchman.body("p", "t", _task())
    assert dispatched[0][1]["reasoning"] == "because"
    assert dispatched[0][1]["sourceTaskId"] == "t"


# ------------------------------------------------------------------- guards

def test_no_observation_refuses(run):
    run(matched=[], concerning=False)
    with pytest.raises(Refusal):
        watchman.body("p", "t", {"input": {"observation": "  "}})


def test_a_plan_with_no_red_flags_refuses_rather_than_pretending_to_monitor(run):
    """Silently monitoring against nothing is the worst outcome: the console
    would show a live monitor that cannot fire."""
    run(matched=[], concerning=False,
        plan={"profile": {"fhirPatientId": "pat-1"},
              "carePlan": {"instructions": [{"id": "i_01", "type": "medication"}]}})
    with pytest.raises(Refusal) as e:
        watchman.body("p", "t", _task())
    assert "return-to-emergency" in e.value.reason


def test_flags_come_from_this_document_not_a_global_list(run):
    """A cardiac discharge and a post-partum discharge must arm different
    monitors from the same agent."""
    flags = watchman._red_flags(PLAN["carePlan"])
    assert "chest pain" in flags and "fainting" in flags
    assert len(flags) == 4
