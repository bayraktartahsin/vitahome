"""Human-terminated tasks — the one door only a person walks back through.

The demo makes a specific claim: escalations cannot be closed by any agent, and
a refusal is answered by a named human choosing from the options the fleet
assembled. That claim is only true if there is exactly one exit and it requires
an actor. These tests are what make it a property rather than a slogan.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fleet import ledger


class _Doc:
    def __init__(self, store, path):
        self._s, self._p = store, path

    @property
    def exists(self):
        return self._p in self._s

    def to_dict(self):
        d = self._s.get(self._p)
        return dict(d) if d else None

    def get(self, transaction=None):
        return self

    def set(self, data, merge=False):
        if merge:
            self._s.setdefault(self._p, {}).update(data)
        else:
            self._s[self._p] = dict(data)

    def update(self, data):
        self._s.setdefault(self._p, {}).update(data)

    def delete(self):
        self._s.pop(self._p, None)

    def collection(self, n):
        return _Coll(self._s, f"{self._p}/{n}")


class _Coll:
    def __init__(self, store, path):
        self._s, self._p = store, path

    def document(self, i):
        return _Doc(self._s, f"{self._p}/{i}")

    def add(self, data):
        self._s.setdefault(f"{self._p}[]", []).append(data)


class _Db:
    def __init__(self):
        self.store = {}

    def collection(self, n):
        return _Coll(self.store, n)

    def transaction(self):
        return None


@pytest.fixture
def db(monkeypatch):
    fake = _Db()
    monkeypatch.setattr(ledger, "db", lambda: fake)
    monkeypatch.setattr(ledger, "bump_ledger", lambda *a, **k: None)
    return fake


def _escalated(db, minutes_ago=10):
    ledger.task_ref("p", "t").set({
        "taskId": "t", "agent": "escalator", "status": "escalated",
        "escalation": {
            "trigger": "chest pain — emergency", "urgency": "emergency",
            "slaStartedAt": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            "resolvedBy": None,
        },
    })


def _refused(db):
    ledger.task_ref("p", "t").set({
        "taskId": "t", "agent": "reconciler", "status": "refused",
        "refusal": {"reason": "Amlodipine — stop or resume?",
                    "options": ["Discontinue amlodipine", "Resume amlodipine"],
                    "at": datetime.now(timezone.utc)},
    })


def _audit(db):
    return db.store.get("patients/p/audit[]", [])


# ------------------------------------------------------------- escalations

def test_a_human_can_close_an_escalation(db):
    _escalated(db)
    out = ledger.resolve_escalation("p", "t", "Dr. Chen", "seen, ECG normal")
    assert out["resolvedBy"] == "Dr. Chen"
    assert db.store["patients/p/tasks/t"]["status"] == "resolved"


def test_the_closing_records_who_and_how_long_they_took(db):
    """An SLA that nobody measures against is decoration."""
    _escalated(db, minutes_ago=7)
    out = ledger.resolve_escalation("p", "t", "Dr. Chen")
    assert 6 * 60 <= out["elapsedSeconds"] <= 8 * 60
    esc = db.store["patients/p/tasks/t"]["escalation"]
    assert esc["resolvedBy"] == "Dr. Chen" and esc["resolvedAt"]


def test_closing_twice_does_not_rewrite_the_first_resolution(db):
    _escalated(db)
    ledger.resolve_escalation("p", "t", "Dr. Chen")
    again = ledger.resolve_escalation("p", "t", "Someone Else")
    assert again["alreadyResolvedBy"] == "Dr. Chen"


def test_a_task_that_is_not_escalated_cannot_be_resolved(db):
    """Guards the claim from the other side: 'resolved' must mean an escalation
    actually happened and a person actually closed it."""
    ledger.task_ref("p", "t").set({"taskId": "t", "status": "done"})
    with pytest.raises(ValueError):
        ledger.resolve_escalation("p", "t", "Dr. Chen")


def test_an_unknown_task_raises_rather_than_silently_succeeding(db):
    with pytest.raises(KeyError):
        ledger.resolve_escalation("p", "nope", "Dr. Chen")


# ---------------------------------------------------------------- refusals

def test_a_human_answers_a_refusal_by_choosing_an_offered_option(db):
    _refused(db)
    out = ledger.decide_refusal("p", "t", "Dr. Chen", "Discontinue amlodipine")
    assert out["decision"] == "Discontinue amlodipine"
    assert db.store["patients/p/tasks/t"]["status"] == "resolved"


def test_the_question_survives_the_answer(db):
    """Six months later the useful record is not 'amlodipine was stopped' — it is
    that the fleet would not choose, and a named person did, from these two
    readings."""
    _refused(db)
    ledger.decide_refusal("p", "t", "Dr. Chen", "Resume amlodipine")
    r = db.store["patients/p/tasks/t"]["refusal"]
    assert r["reason"] == "Amlodipine — stop or resume?"
    assert len(r["options"]) == 2
    assert r["decidedBy"] == "Dr. Chen" and r["decision"] == "Resume amlodipine"


def test_an_option_nobody_offered_is_rejected(db):
    """The fleet assembled the choices. A caller cannot invent a third one and
    have it recorded as though the fleet had proposed it."""
    _refused(db)
    with pytest.raises(ValueError):
        ledger.decide_refusal("p", "t", "Dr. Chen", "Double the dose")


def test_deciding_twice_keeps_the_first_decision(db):
    _refused(db)
    ledger.decide_refusal("p", "t", "Dr. Chen", "Discontinue amlodipine")
    again = ledger.decide_refusal("p", "t", "Dr. Patel", "Resume amlodipine")
    assert again["alreadyDecidedBy"] == "Dr. Chen"
    assert db.store["patients/p/tasks/t"]["refusal"]["decision"] == "Discontinue amlodipine"


# ------------------------------------------------------------------- audit

def test_both_human_actions_name_the_human_in_the_audit_trail(db):
    _escalated(db)
    ledger.resolve_escalation("p", "t", "Dr. Chen", "reviewed")
    _refused(db)
    ledger.decide_refusal("p", "t", "Dr. Patel", "Resume amlodipine")
    details = " ".join(a["detail"] for a in _audit(db))
    assert "Dr. Chen" in details and "Dr. Patel" in details
