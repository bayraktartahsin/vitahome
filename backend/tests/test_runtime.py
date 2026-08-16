"""Runtime lifecycle — retry semantics and the poison-message guard.

The drill depends on failures being redelivered. But a deterministically-failing
task would then retry forever and starve the fleet, so there is a hard attempt
ceiling after which the task is dead-lettered to the human queue and ACKed.
These tests pin both halves of that contract.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.fleet import runtime
from app.fleet.runtime import Escalation, Refusal


class _Ledger:
    def __init__(self, attempt: int = 1):
        self.attempt = attempt
        self.events: list[tuple[str, str]] = []

    # --- surface used by runtime ---
    SETTLED = {"done", "refused", "escalated", "resolved"}

    def peek(self, pid, task_id):
        return None                      # not yet started, unless overridden

    def audit(self, pid, kind, actor, detail, task_id=None, extra=None):
        pass

    def claim(self, pid, task_id, worker):
        return {"attempt": self.attempt, "agent": "scheduler", "error": "boom"}

    def beat(self, pid, task_id):
        pass

    def complete(self, pid, task_id, agent, summary):
        self.events.append(("complete", summary))

    def refuse(self, pid, task_id, agent, reason, options):
        self.events.append(("refuse", reason))

    def escalate(self, pid, task_id, agent, trigger, context):
        self.events.append(("escalate", trigger))

    def fail(self, pid, task_id, agent, err):
        self.events.append(("fail", err))


@pytest.fixture(autouse=True)
def _fast_heartbeat(monkeypatch):
    monkeypatch.setattr(settings, "heartbeat_seconds", 3600)   # never fires in a test


def test_successful_task_completes(monkeypatch):
    led = _Ledger()
    monkeypatch.setattr(runtime, "ledger", led)
    out = runtime.run_task("scheduler", "p", "t", lambda *_: "booked cardiology")
    assert out["status"] == "done"
    assert led.events == [("complete", "booked cardiology")]


def test_refusal_is_terminal_and_not_retried(monkeypatch):
    """A refusal must NOT raise — raising would make Pub/Sub redeliver, and the
    fleet would keep re-asking a question it already handed to a human."""
    led = _Ledger()
    monkeypatch.setattr(runtime, "ledger", led)

    def _body(*_):
        raise Refusal("ambiguous instruction", ["option a", "option b"])

    out = runtime.run_task("reconciler", "p", "t", _body)
    assert out["status"] == "refused"
    assert led.events[0][0] == "refuse"


def test_escalation_is_terminal_and_not_retried(monkeypatch):
    led = _Ledger()
    monkeypatch.setattr(runtime, "ledger", led)

    def _body(*_):
        raise Escalation("chest pain reported")

    out = runtime.run_task("watchman", "p", "t", _body)
    assert out["status"] == "escalated"


def test_genuine_failure_reraises_so_pubsub_redelivers(monkeypatch):
    """This is the recovery mechanism: an unacked message comes back."""
    led = _Ledger()
    monkeypatch.setattr(runtime, "ledger", led)

    def _body(*_):
        raise ValueError("FHIR 400")

    with pytest.raises(ValueError):
        runtime.run_task("scheduler", "p", "t", _body)
    assert ("fail", "FHIR 400") in led.events


def test_poison_message_is_dead_lettered_not_retried_forever(monkeypatch):
    """Past the attempt ceiling the task goes to the human queue and the
    handler returns normally, ACKing the message so the loop stops."""
    led = _Ledger(attempt=settings.max_attempts + 1)
    monkeypatch.setattr(runtime, "ledger", led)

    def _never_called(*_):
        raise AssertionError("body must not run once the ceiling is passed")

    out = runtime.run_task("scheduler", "p", "t", _never_called)
    assert out["status"] == "dead_letter"
    assert led.events[0][0] == "escalate"
    assert "dead-lettered" in led.events[0][1]


def test_attempt_ceiling_allows_normal_retries(monkeypatch):
    """A second attempt (the drill's recovery) must still execute."""
    led = _Ledger(attempt=2)
    monkeypatch.setattr(runtime, "ledger", led)
    out = runtime.run_task("scheduler", "p", "t", lambda *_: "recovered")
    assert out["status"] == "done"
    assert out["attempt"] == 2


# --------------------------------------------------------------------------
# Redelivery of finished work
# --------------------------------------------------------------------------

class _SettledLedger(_Ledger):
    """A ledger whose task is already in a terminal state."""

    SETTLED = {"done", "refused", "escalated", "resolved"}

    def __init__(self, status: str, attempt: int = 3):
        super().__init__(attempt=attempt)
        self.status = status
        self.claimed = False
        self.audits: list[tuple] = []

    def peek(self, pid, task_id):
        return {"status": self.status, "attempt": self.attempt, "agent": "scheduler"}

    def claim(self, pid, task_id, worker):
        self.claimed = True
        return super().claim(pid, task_id, worker)

    def audit(self, pid, kind, actor, detail, task_id=None, extra=None):
        self.audits.append((kind, detail))


@pytest.mark.parametrize("status", ["done", "refused", "escalated", "resolved"])
def test_a_redelivery_after_settling_does_no_work(monkeypatch, status):
    """At-least-once delivery means duplicates are routine. A settled task must
    be acked untouched — never claimed, never re-run."""
    led = _SettledLedger(status)
    monkeypatch.setattr(runtime, "ledger", led)
    ran = []
    out = runtime.run_task("scheduler", "p", "t", lambda *_: ran.append(1) or "x")

    assert out["status"] == f"already_{status}"
    assert not led.claimed, "a settled task was claimed, which resurrects it"
    assert ran == [], "the agent body re-ran on a settled task"


def test_the_duplicate_delivery_is_visible_in_the_audit_trail(monkeypatch):
    """Silently swallowing duplicates hides how often they happen."""
    led = _SettledLedger("done")
    monkeypatch.setattr(runtime, "ledger", led)
    runtime.run_task("scheduler", "p", "t", lambda *_: "x")
    assert any("already done" in d for _, d in led.audits)


def test_a_completed_task_can_never_dead_letter_itself(monkeypatch):
    """The actual defect. A finished task redelivered past the attempt ceiling
    walked its own counter up and escalated as "failed 6 times", with all its
    steps sitting there completed."""
    led = _SettledLedger("done", attempt=settings.max_attempts + 5)
    monkeypatch.setattr(runtime, "ledger", led)
    out = runtime.run_task("scheduler", "p", "t", lambda *_: "x")

    assert out["status"] == "already_done"
    assert not any(e[0] == "escalate" for e in led.events), \
        "a successful task was dead-lettered into the clinician queue"


def test_an_unstarted_task_is_still_claimed_normally(monkeypatch):
    led = _SettledLedger("pending", attempt=1)
    monkeypatch.setattr(runtime, "ledger", led)
    runtime.run_task("scheduler", "p", "t", lambda *_: "booked")
    assert led.claimed
