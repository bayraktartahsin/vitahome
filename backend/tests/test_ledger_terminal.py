"""Terminal transitions must happen exactly once, even under replay.

Redelivery after a task has already finished is normal, not exotic: Pub/Sub's
ack deadline can expire while the final step is still running. The step ledger
already makes the *side effects* safe. This pins the other half — that the
status flip and the Autonomy Ledger counter also refuse to run twice.

It matters because the Autonomy Ledger is a number we put on screen and defend.
A counter that inflates on redelivery would be a lie told by a bug.
"""
from __future__ import annotations

import pytest

from app.fleet import ledger


# --------------------------------------------------------------------------
# A Firestore double. Small on purpose — it supports exactly the operations
# ledger.py performs, so a new access pattern fails loudly instead of silently
# passing against a permissive mock.
# --------------------------------------------------------------------------

class _Doc:
    def __init__(self, store: dict, path: str):
        self._store, self._path = store, path

    # read
    @property
    def exists(self) -> bool:
        return self._path in self._store

    def to_dict(self) -> dict | None:
        d = self._store.get(self._path)
        return dict(d) if d is not None else None

    def get(self, transaction=None) -> "_Doc":
        return self

    # write
    def set(self, data: dict, merge: bool = False) -> None:
        if merge:
            cur = self._store.setdefault(self._path, {})
            for k, v in data.items():
                cur[k] = cur.get(k, 0) + v.value if isinstance(v, _Increment) else v
        else:
            self._store[self._path] = dict(data)

    def update(self, data: dict) -> None:
        self._store.setdefault(self._path, {}).update(data)

    def collection(self, name: str) -> "_Coll":
        return _Coll(self._store, f"{self._path}/{name}")


class _Coll:
    def __init__(self, store: dict, path: str):
        self._store, self._path = store, path

    def document(self, doc_id: str) -> _Doc:
        return _Doc(self._store, f"{self._path}/{doc_id}")

    def add(self, data: dict) -> None:
        self._store.setdefault(f"{self._path}[]", []).append(data)


class _Db:
    def __init__(self):
        self.store: dict = {}

    def collection(self, name: str) -> _Coll:
        return _Coll(self.store, name)

    def transaction(self) -> "_Tx":
        return _Tx()


class _Tx:
    """Firestore transactions write through ``tx.update(ref, data)``, not
    ``ref.update(data)`` — mirroring that keeps the code under test honest."""

    def update(self, ref: _Doc, data: dict) -> None:
        ref.update(data)


class _Increment:
    def __init__(self, value: int):
        self.value = value


class _FakeFirestore:
    """Stands in for the ``firestore`` module inside ledger.py.

    ``transactional`` runs the body straight through. That is a fair model here:
    the guard's correctness rests on read-then-conditional-write inside the
    transaction, and this test drives the two calls sequentially — which is the
    ordering that actually caused the bug in production.
    """
    Increment = _Increment
    Transaction = object

    @staticmethod
    def transactional(fn):
        return lambda tx: fn(tx)


@pytest.fixture
def db(monkeypatch) -> _Db:
    fake = _Db()
    monkeypatch.setattr(ledger, "firestore", _FakeFirestore)
    monkeypatch.setattr(ledger, "db", lambda: fake)
    ledger.task_ref("p", "t").set({"taskId": "t", "status": "leased", "steps": []})
    return fake


def _counts(db: _Db) -> dict:
    return db.store.get("ledger/p", {})


def _audit_kinds(db: _Db) -> list[str]:
    return [a["kind"] for a in db.store.get("patients/p/audit[]", [])]


# --------------------------------------------------------------------------

def test_complete_flips_status_and_counts_once(db):
    ledger.complete("p", "t", "scheduler", "booked cardiology")
    assert db.store["patients/p/tasks/t"]["status"] == "done"
    assert _counts(db)["autonomous"] == 1


def test_replay_after_completion_does_not_double_count(db):
    """The exact bug: a redelivery arriving after the task finished counted
    one booking as two."""
    ledger.complete("p", "t", "scheduler", "booked cardiology")
    ledger.complete("p", "t", "scheduler", "booked cardiology")

    assert _counts(db)["autonomous"] == 1, "redelivery inflated the Autonomy Ledger"
    assert _audit_kinds(db).count("action") == 1
    assert "skip" in _audit_kinds(db), "the replay should still be visible in the audit trail"


def test_refusal_counts_once_and_does_not_become_done(db):
    ledger.refuse("p", "t", "reconciler", "two plausible readings", ["resume", "hold"])
    ledger.refuse("p", "t", "reconciler", "two plausible readings", ["resume", "hold"])

    assert _counts(db)["refused"] == 1
    assert db.store["patients/p/tasks/t"]["status"] == "refused"


def test_a_terminal_task_cannot_be_overwritten_by_another_outcome(db):
    """A late replay must not turn a refusal into a completion. The human's
    decision point has to survive."""
    ledger.refuse("p", "t", "reconciler", "ambiguous", [])
    ledger.complete("p", "t", "reconciler", "done anyway")

    assert db.store["patients/p/tasks/t"]["status"] == "refused"
    assert _counts(db).get("autonomous", 0) == 0


def test_failed_is_not_terminal_so_a_retry_can_still_succeed(db):
    """Retry is the recovery mechanism; a failure must never wedge the task."""
    ledger.fail("p", "t", "scheduler", "FHIR 503")
    ledger.complete("p", "t", "scheduler", "booked on retry")

    assert db.store["patients/p/tasks/t"]["status"] == "done"
    assert _counts(db)["autonomous"] == 1
