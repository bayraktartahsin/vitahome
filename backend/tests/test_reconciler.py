"""Reconciler — the boundary between advice and action.

Gemini flags conflicts. Only the code below decides whether a flag becomes an
applied change or a refusal. These tests exist because that boundary is the
single most safety-relevant line in the project: if a model could ever talk the
Reconciler into applying something it marked ambiguous, the whole thesis is
decoration.

Everything here is deterministic. The model's output is supplied as a fixture,
so the assertions are about our branching, not about what a model said today.
"""
from __future__ import annotations

import pytest

from app.agents import reconciler
from app.fleet.runtime import Refusal


class _Doc:
    def __init__(self, data: dict):
        self.data = data
        self.merged: dict = {}

    exists = True

    def to_dict(self):
        return self.data

    def get(self):
        return self

    def set(self, data, merge=False):
        self.merged.update(data)

    def collection(self, _name):
        return self

    def document(self, _id):
        return self

    def add(self, _data):
        pass


PLAN = {
    "profile": {"fhirPatientId": "pat-1"},
    "carePlan": {"instructions": [
        {"id": "i_01", "type": "medication", "text": "Aspirin 81 mg PO daily"},
        {"id": "i_05", "type": "medication_stop", "text": "STOP amlodipine 5 mg"},
        {"id": "i_06", "type": "other", "text": "Resume home medications as previously prescribed"},
    ]},
}

ACTIVE = [
    {"id": "mr-amlo", "drug": "Amlodipine 5 mg", "dose": "5 mg PO daily"},
    {"id": "mr-asa", "drug": "Aspirin 81 mg", "dose": "81 mg PO daily"},
]

CONFLICT = {
    "drug": "Amlodipine",
    "question": "should amlodipine be stopped or resumed?",
    "readings": [
        {"reading": "Stop amlodipine", "source": "line 11",
         "consequence": "patient takes metoprolol only"},
        {"reading": "Resume amlodipine", "source": "line 14",
         "consequence": "patient takes both agents"},
    ],
}


@pytest.fixture
def run(monkeypatch):
    """Drive body() with canned FHIR + model responses, recording FHIR writes."""

    def _go(changes: list[dict], conflicts: list[dict], active=ACTIVE):
        doc = _Doc(dict(PLAN))
        writes: list[tuple[str, str]] = []
        steps: dict = {}

        monkeypatch.setattr(reconciler.ledger, "db", lambda: doc)
        monkeypatch.setattr(reconciler.ledger, "bump_ledger", lambda *a, **k: None)
        monkeypatch.setattr(reconciler.ledger, "audit", lambda *a, **k: None)
        # run_step is exercised for real elsewhere; here it just executes the body
        # so these tests stay about the decision, not about the ledger.
        monkeypatch.setattr(
            reconciler.ledger, "run_step",
            lambda pid, tid, agent, name, fn: steps.setdefault(name, fn(f"{tid}:{name}")),
        )
        monkeypatch.setattr(reconciler, "_active_medications", lambda _p: active)
        monkeypatch.setattr(
            reconciler.gemini, "generate_json",
            lambda *a, **k: ({"changes": changes, "conflicts": conflicts},
                             {"model": "gemini-3.7-flash", "latencyMs": 2350}),
        )
        monkeypatch.setattr(reconciler.fhir, "read",
                            lambda rt, rid: {"id": rid, "status": "active"})
        monkeypatch.setattr(reconciler.fhir, "update",
                            lambda rt, rid, b: writes.append(("update", rid)) or {"id": rid})
        monkeypatch.setattr(reconciler.fhir, "create",
                            lambda rt, b, idem=None: writes.append(
                                ("create", b["medicationCodeableConcept"]["text"])) or {"id": "new"})

        return doc, writes, steps

    return _go


# ------------------------------------------------------------- The Refusal

def test_a_conflict_refuses_instead_of_choosing(run):
    doc, _, _ = run(changes=[], conflicts=[CONFLICT])
    with pytest.raises(Refusal) as e:
        reconciler.body("p", "t", {})
    assert "Amlodipine" in e.value.reason


def test_the_refusal_hands_over_both_readings_not_a_complaint(run):
    """A refusal that only says 'I could not decide' moves the work to the human
    without moving any of the analysis. Both readings, with their sources, must
    travel with it."""
    run(changes=[], conflicts=[CONFLICT])
    with pytest.raises(Refusal) as e:
        reconciler.body("p", "t", {})
    opts = e.value.options
    assert any("Stop amlodipine" in o and "line 11" in o for o in opts)
    assert any("Resume amlodipine" in o and "line 14" in o for o in opts)
    assert any("clarify" in o.lower() for o in opts)


def test_a_flagged_drug_is_never_written_to_fhir(run):
    """The load-bearing assertion. The model flagged amlodipine AND listed a stop
    for it — a plausible model slip. The code must ignore the change."""
    _, writes, _ = run(
        changes=[{"drug": "Amlodipine", "action": "stop", "activeRequestId": "mr-amlo",
                  "rationale": "line 11 says stop"}],
        conflicts=[CONFLICT],
    )
    with pytest.raises(Refusal):
        reconciler.body("p", "t", {})
    assert writes == [], f"a conflicted drug reached the clinical record: {writes}"


def test_the_conflict_is_persisted_for_the_console(run):
    doc, _, _ = run(changes=[], conflicts=[CONFLICT])
    with pytest.raises(Refusal):
        reconciler.body("p", "t", {})
    assert doc.merged["openConflicts"][0]["drug"] == "Amlodipine"


# --------------------------------------------------- unambiguous work still runs

def test_undisputed_changes_apply_even_when_something_else_is_refused(run):
    """Safety that blocks four uncontested changes to protect one contested one
    is safety nobody keeps switched on."""
    _, writes, _ = run(
        changes=[
            {"drug": "Ticagrelor 90 mg", "action": "start", "rationale": "new on discharge"},
            {"drug": "Aspirin 81 mg", "action": "continue", "rationale": "already active"},
            {"drug": "Amlodipine", "action": "stop", "activeRequestId": "mr-amlo",
             "rationale": "line 11"},
        ],
        conflicts=[CONFLICT],
    )
    with pytest.raises(Refusal):
        reconciler.body("p", "t", {})
    assert ("create", "Ticagrelor 90 mg") in writes
    assert not any(w[0] == "update" for w in writes)   # amlodipine untouched


def test_a_clean_reconciliation_completes_without_refusing(run):
    _, writes, _ = run(
        changes=[{"drug": "Metoprolol 25 mg", "action": "start", "rationale": "new"}],
        conflicts=[],
    )
    summary = reconciler.body("p", "t", {})
    assert "1 medication change" in summary
    assert ("create", "Metoprolol 25 mg") in writes


def test_stop_without_a_matching_record_is_not_invented(run):
    """No activeRequestId means we never found the thing we were told to stop.
    Silently doing nothing is right; fabricating a resource to stop is not."""
    _, writes, _ = run(
        changes=[{"drug": "Furosemide", "action": "stop", "rationale": "line 11"}],
        conflicts=[],
    )
    reconciler.body("p", "t", {})
    assert writes == []


def test_conflict_matching_is_case_and_space_insensitive(run):
    """The model writes 'amlodipine ' in one list and 'Amlodipine' in the other.
    A whitespace difference must not become an unguarded write."""
    _, writes, _ = run(
        changes=[{"drug": " amlodipine ", "action": "stop", "activeRequestId": "mr-amlo",
                  "rationale": "x"}],
        conflicts=[{**CONFLICT, "drug": "Amlodipine"}],
    )
    with pytest.raises(Refusal):
        reconciler.body("p", "t", {})
    assert writes == []


# ------------------------------------------------------------------ guards

def test_missing_patient_record_refuses_rather_than_guessing(run):
    doc, _, _ = run(changes=[], conflicts=[])
    doc.data = {"profile": {}, "carePlan": PLAN["carePlan"]}
    with pytest.raises(Refusal) as e:
        reconciler.body("p", "t", {})
    assert "FHIR patient record" in e.value.reason


def test_nothing_to_reconcile_refuses_rather_than_reporting_success(run):
    doc, _, _ = run(changes=[], conflicts=[])
    doc.data = {"profile": {"fhirPatientId": "pat-1"}, "carePlan": {"instructions": []}}
    with pytest.raises(Refusal):
        reconciler.body("p", "t", {})
