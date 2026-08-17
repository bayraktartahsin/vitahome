"""Supervisor — detects a dead worker's abandoned lease.

This file exists because the supervisor shipped on day one, was described in the
architecture, and had never once been executed. The moment it was finally
scheduled it returned 500: its collection-group query needs a Firestore index
that is not created automatically.

Nothing caught that, because nothing called it. So these run the logic directly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fleet import supervisor


class _Ref:
    """Mirrors the shape scan_stale actually walks: a task document's
    reference.parent.parent.id is the patient id it lives under."""

    def __init__(self, pid, updates):
        self.parent = type("Coll", (), {"parent": type("Doc", (), {"id": pid})()})()
        self._updates = updates

    def update(self, data):
        self._updates.append(data)


class _Snap:
    def __init__(self, data, pid="p_hero", updates=None):
        self._d = data
        self.reference = _Ref(pid, updates if updates is not None else [])

    def to_dict(self):
        return self._d


@pytest.fixture
def db(monkeypatch):
    state = {"rows": [], "audits": []}

    class _Q:
        def where(self, *a, **k):
            return self

        def limit(self, n):
            return self

        def stream(self):
            return iter(state["rows"])

    class _Db:
        def collection_group(self, name):
            return _Q()

    monkeypatch.setattr(supervisor, "db", lambda: _Db())
    monkeypatch.setattr(supervisor, "audit",
                        lambda *a, **k: state["audits"].append(a))
    return state


def _task(seconds_stale: int, **kw):
    now = datetime.now(timezone.utc)
    return _Snap({
        "taskId": "t_1", "agent": "scheduler", "status": "leased",
        "leasedBy": "nj4-f7210a",
        "heartbeatAt": now - timedelta(seconds=seconds_stale),
        **kw,
    })


def test_a_fresh_lease_is_left_alone(db):
    db["rows"] = [_task(seconds_stale=2)]
    assert supervisor.scan_stale() == []
    assert db["audits"] == []


def test_a_stale_lease_is_flagged(db):
    """A worker that died without writing anything leaves exactly this: a task
    still marked leased, with a heartbeat that stopped."""
    db["rows"] = [_task(seconds_stale=600)]
    out = supervisor.scan_stale()
    assert len(out) == 1
    assert out[0]["patient"] == "p_hero" and out[0]["agent"] == "scheduler"
    assert any("AGENT_DOWN" in str(a) for a in db["audits"])


def test_the_flagged_task_is_marked_so_it_is_not_reported_again(db):
    updates: list = []
    db["rows"] = [_task(seconds_stale=600)]
    db["rows"][0].reference._updates = updates
    supervisor.scan_stale()
    assert updates == [{"downFlagged": True}]


def test_a_task_with_no_heartbeat_is_skipped_not_flagged(db):
    """claim() always stamps heartbeatAt, so a leased task without one is not a
    dead worker — it is a shape that should not exist. Skipping is right;
    inventing an AGENT_DOWN from missing data would be noise."""
    t = _task(seconds_stale=600)
    t._d["heartbeatAt"] = None
    db["rows"] = [t]
    assert supervisor.scan_stale() == []


def test_the_grace_period_is_configurable(db):
    db["rows"] = [_task(seconds_stale=30)]
    assert supervisor.scan_stale(grace_seconds=600) == []
    assert len(supervisor.scan_stale(grace_seconds=5)) == 1


def test_scanning_twice_does_not_flag_the_same_task_again(db):
    """The console renders one red gap per death, not one per sweep."""
    t = _task(seconds_stale=600)
    db["rows"] = [t]
    supervisor.scan_stale()
    first = len(db["audits"])
    t._d["downFlagged"] = True
    db["rows"] = [t]
    supervisor.scan_stale()
    assert len(db["audits"]) == first, "the same dead worker was reported twice"
