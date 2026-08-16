"""Coach — one question, and the right to ask nothing.

The failure mode of every check-in product is asking a question with no wrong
answer, every day, until people stop reading. So the behaviour worth pinning is
that the Coach can decline to send anything, and that it never decides what an
answer means — answers go to the Watchman, which owns this document's red flags.
"""
from __future__ import annotations

import pytest

from app.agents import coach
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


PLAN = {
    "profile": {"fhirPatientId": "pat-1"},
    "carePlan": {"instructions": [
        {"id": "i_02", "text": "Ticagrelor — DO NOT STOP", "criticality": "CRITICAL"},
        {"id": "i_10", "text": "No driving for 3 days", "criticality": "none"},
    ]},
    "openConflicts": [{"drug": "Amlodipine", "question": "stop or resume?"}],
}


@pytest.fixture
def run(monkeypatch):
    def _go(verdict, plan=PLAN):
        doc = _Doc({k: dict(v) if isinstance(v, dict) else v for k, v in plan.items()})
        audits: list = []
        prompts: list[str] = []
        monkeypatch.setattr(coach.ledger, "db", lambda: doc)
        monkeypatch.setattr(coach.ledger, "bump_ledger", lambda *a, **k: None)
        monkeypatch.setattr(coach.ledger, "audit", lambda *a, **k: audits.append(a))
        monkeypatch.setattr(coach.ledger, "run_step",
                            lambda pid, tid, ag, name, fn: fn(f"{tid}:{name}"))
        monkeypatch.setattr(coach, "_recent_reports", lambda _p, limit=8: [])
        monkeypatch.setattr(coach.fhir, "create", lambda rt, b, idem=None: {"id": "obs-1"})

        def _gen(prompt, *a, **k):
            prompts.append(prompt)
            return verdict, {"model": "gemini-3.7-flash", "latencyMs": 1800}

        monkeypatch.setattr(coach.gemini, "generate_json", _gen)
        return doc, audits, prompts

    return _go


def _q(**kw):
    return {"worthAsking": True, "question": "Have you felt dizzy standing up?",
            "why": "would settle the amlodipine question", "about": "dizziness",
            "listenFor": ["yes", "nearly fell"], **kw}


# ------------------------------------------------------------------ asking

def test_it_asks_one_question_and_records_it(run):
    doc, _, _ = run(_q())
    summary = coach.body("p", "t", {})
    assert "dizziness" in summary
    open_q = doc.merged["openCheckIn"]
    assert open_q["question"] == "Have you felt dizzy standing up?"
    assert open_q["answer"] is None
    assert open_q["listenFor"] == ["yes", "nearly fell"]


def test_the_asking_is_part_of_the_clinical_record(run):
    """A question that was asked and never answered is itself information."""
    doc, _, _ = run(_q())
    coach.body("p", "t", {})
    assert doc.merged["openCheckIn"]["ref"] == "Observation/obs-1"


def test_it_is_told_what_is_still_waiting_on_a_human(run):
    """The highest-value question is usually the one that would settle an open
    clinical decision, so the open conflicts have to reach the prompt."""
    _, _, prompts = run(_q())
    coach.body("p", "t", {})
    assert "Amlodipine" in prompts[0] and "stop or resume?" in prompts[0]


def test_it_is_told_what_it_already_asked(run):
    """Otherwise it asks about dizziness every morning forever."""
    plan = {**PLAN, "carePlan": {**PLAN["carePlan"],
                                 "checkIns": [{"about": "wound-site"}, {"about": "dizziness"}]}}
    _, _, prompts = run(_q(), plan=plan)
    coach.body("p", "t", {})
    assert "wound-site" in prompts[0] and "dizziness" in prompts[0]


# ---------------------------------------------------------- asking nothing

def test_it_may_decide_there_is_nothing_worth_asking(run):
    """An unnecessary check-in is how people learn to ignore the necessary one."""
    doc, audits, _ = run(_q(worthAsking=False, why="nothing new since yesterday"))
    summary = coach.body("p", "t", {})
    assert "no check-in today" in summary
    assert "openCheckIn" not in doc.merged, "a skipped check-in must not open one"
    assert any("no check-in sent" in str(a) for a in audits)


# ------------------------------------------------------------------ guards

def test_no_care_plan_refuses(run):
    run(_q(), plan={"profile": {"fhirPatientId": "pat-1"}, "carePlan": {}})
    with pytest.raises(Refusal) as e:
        coach.body("p", "t", {})
    assert "no care plan" in e.value.reason


def test_it_only_reports_critical_instructions_as_critical(run):
    """The prompt gets the instructions that matter, not the whole plan — a
    check-in about not driving is not worth anyone's morning."""
    _, _, prompts = run(_q())
    coach.body("p", "t", {})
    assert "DO NOT STOP" in prompts[0]
    assert "No driving" not in prompts[0]
