"""The task ledger — VitaHome's durability core.

Every side-effecting thing an agent does is a **step** with a deterministic
idempotency key (``{taskId}:{stepName}``). Steps are appended to the task
document in Firestore *after* the effect succeeds. When an agent is killed
mid-task (see ``chaos.py``) Pub/Sub redelivers the message and the replaying
agent skips every step already recorded.

That is the whole Failure Drill: at-least-once delivery + idempotent steps
= effectively-once execution. There is no exactly-once; we don't pretend.

Design notes for reviewers:
  * The side effect runs OUTSIDE the Firestore transaction. Transactions retry,
    and retrying a calendar booking would double-book. We execute, then commit
    the record transactionally with a re-check.
  * External writes additionally carry the idempotency key into the remote
    system (FHIR resource ``identifier``, Calendar ``iCalUID``) so even a crash
    in the gap between "effect done" and "step recorded" cannot duplicate.
  * ``audit`` is append-only and is the UI's event source. The gap left by a
    killed agent is never erased — the scar is the proof.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

from google.cloud import firestore

from ..config import settings

TaskStatus = Literal["pending", "leased", "done", "refused", "escalated", "failed"]
TERMINAL = frozenset({"done", "refused", "escalated"})
"""States a task never leaves. ``failed`` is deliberately absent — a failed task
is expected to be redelivered and retried."""
AuditKind = Literal[
    "heartbeat", "action", "AGENT_DOWN", "redelivery",
    "skip", "refusal", "escalation", "access", "lease",
]

_db: firestore.Client | None = None


def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=settings.gcp_project)
    return _db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def task_ref(pid: str, task_id: str):
    return db().collection("patients").document(pid).collection("tasks").document(task_id)


def idem_key(task_id: str, step_name: str) -> str:
    """Deterministic across every replay of this task — the whole trick."""
    return f"{task_id}:{step_name}"


# --------------------------------------------------------------------------
# audit — append-only event source for the console
# --------------------------------------------------------------------------

def audit(pid: str, kind: AuditKind, actor: str, detail: str, task_id: str | None = None,
          extra: dict[str, Any] | None = None) -> None:
    db().collection("patients").document(pid).collection("audit").add({
        "at": _now(),
        "kind": kind,
        "actor": actor,
        "detail": detail,
        "taskId": task_id,
        **(extra or {}),
    })


# --------------------------------------------------------------------------
# task lifecycle
# --------------------------------------------------------------------------

def create_task(pid: str, agent: str, instruction_id: str | None = None,
                payload: dict[str, Any] | None = None) -> str:
    task_id = f"t_{uuid.uuid4().hex[:12]}"
    task_ref(pid, task_id).set({
        "taskId": task_id,
        "agent": agent,
        "instructionId": instruction_id,
        "status": "pending",
        "attempt": 0,
        "leasedBy": None,
        "heartbeatAt": None,
        "leaseExpiresAt": None,
        "input": payload or {},
        "steps": [],
        "refusal": None,
        "escalation": None,
        "createdAt": _now(),
    })
    audit(pid, "action", agent, f"task created ({agent})", task_id)
    return task_id


def claim(pid: str, task_id: str, worker_id: str) -> dict[str, Any]:
    """Lease the task for this worker and bump the attempt counter.

    A second attempt means Pub/Sub redelivered — i.e. the previous worker died.
    We record that explicitly so the console can render the recovery.
    """
    ref = task_ref(pid, task_id)
    snap = ref.get()
    if not snap.exists:
        raise KeyError(f"task {task_id} not found for {pid}")
    data = snap.to_dict()
    attempt = int(data.get("attempt", 0)) + 1

    ref.update({
        "status": "leased",
        "attempt": attempt,
        "leasedBy": worker_id,
        "heartbeatAt": _now(),
        "leaseExpiresAt": _now() + timedelta(seconds=settings.lease_seconds),
    })
    if attempt > 1:
        audit(pid, "redelivery", data.get("agent", "?"),
              f"redelivered — attempt {attempt} (previous worker did not finish)", task_id,
              {"attempt": attempt})
    audit(pid, "lease", data.get("agent", "?"), f"leased by {worker_id}", task_id)
    return {**data, "attempt": attempt}


def beat(pid: str, task_id: str) -> None:
    """Liveness. The supervisor watches for these going stale."""
    task_ref(pid, task_id).update({
        "heartbeatAt": _now(),
        "leaseExpiresAt": _now() + timedelta(seconds=settings.lease_seconds),
    })


def completed_steps(pid: str, task_id: str) -> dict[str, dict[str, Any]]:
    snap = task_ref(pid, task_id).get()
    steps = (snap.to_dict() or {}).get("steps", []) if snap.exists else []
    return {s["name"]: s for s in steps}


# --------------------------------------------------------------------------
# THE step executor
# --------------------------------------------------------------------------

def run_step(pid: str, task_id: str, agent: str, step_name: str,
             fn: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """Execute ``fn`` exactly once across all replays of this task.

    ``fn`` receives the idempotency key so it can propagate it into the remote
    system (FHIR identifier / Calendar iCalUID) and search-before-create.
    """
    key = idem_key(task_id, step_name)

    # 1. Already done in a previous life? Skip, loudly (the console renders this).
    done = completed_steps(pid, task_id)
    if step_name in done:
        audit(pid, "skip", agent, f"step '{step_name}' already completed — skipped on replay",
              task_id, {"idempotencyKey": key})
        return done[step_name].get("result", {})

    # 2. If this agent has been armed on the chaos panel, die here — inside the
    #    step, before the side effect, with the message still unacked.
    #    Imported lazily: chaos imports from this module.
    from . import chaos
    if chaos.consume_if_armed(agent, pid, task_id, step_name):
        return {}          # unreachable — the process is gone

    # 3. Demo-only window that widens the kill target for a hand-timed kill.
    #    Scoped to ONE named step so the window is predictable on camera and
    #    normal task duration stays well inside the Pub/Sub ack deadline.
    if settings.drill_slow_seconds > 0 and step_name == settings.drill_slow_step:
        audit(pid, "action", agent,
              f"drill window open on '{step_name}' — {settings.drill_slow_seconds}s to kill me",
              task_id, {"drillWindow": True})
        time.sleep(settings.drill_slow_seconds)

    # 3. Side effect — deliberately OUTSIDE any transaction.
    result = fn(key) or {}

    # 4. Record it transactionally, re-checking in case of a concurrent replay.
    ref = task_ref(pid, task_id)

    @firestore.transactional
    def _append(tx: firestore.Transaction) -> None:
        snap = ref.get(transaction=tx)
        steps = (snap.to_dict() or {}).get("steps", [])
        if any(s["name"] == step_name for s in steps):
            return  # someone else won the race; their record stands
        steps.append({
            "name": step_name,
            "idempotencyKey": key,
            "result": result,
            "externalRef": result.get("externalRef"),
            "at": _now(),
        })
        tx.update(ref, {"steps": steps})

    _append(db().transaction())
    audit(pid, "action", agent, f"step '{step_name}' completed", task_id,
          {"idempotencyKey": key, "externalRef": result.get("externalRef")})
    return result


# --------------------------------------------------------------------------
# terminal transitions
# --------------------------------------------------------------------------

def _enter_terminal(pid: str, task_id: str, fields: dict[str, Any]) -> bool:
    """Move a task to a terminal state, once.

    A task can legitimately be delivered again *after* it finished — the ack
    deadline can expire while the last step is still running. The replay is
    harmless (every step gets skipped) but the terminal transition must not run
    twice, or the Autonomy Ledger counts one booking as two. The ledger is a
    number we put on screen and defend, so it is guarded here rather than
    trusted to happen once.

    Returns True if this call is the one that made the transition.
    """
    ref = task_ref(pid, task_id)

    @firestore.transactional
    def _tx(tx: firestore.Transaction) -> bool:
        snap = ref.get(transaction=tx)
        if (snap.to_dict() or {}).get("status") in TERMINAL:
            return False
        tx.update(ref, fields)
        return True

    return _tx(db().transaction())


def complete(pid: str, task_id: str, agent: str, summary: str = "") -> None:
    first = _enter_terminal(pid, task_id, {"status": "done", "completedAt": _now()})
    if not first:
        audit(pid, "skip", agent, "task already complete — replay produced no new effect",
              task_id)
        return
    audit(pid, "action", agent, summary or "task complete", task_id)
    bump_ledger(pid, "autonomous")


def refuse(pid: str, task_id: str, agent: str, reason: str,
           options: list[str] | None = None) -> None:
    """The thesis, as a state transition.

    The fleet declines to act on an ambiguous instruction and hands a human a
    decision with the options pre-assembled. Calibrated non-autonomy.
    """
    if not _enter_terminal(pid, task_id, {
        "status": "refused",
        "refusal": {"reason": reason, "options": options or [], "at": _now()},
    }):
        return
    audit(pid, "refusal", agent, f"declined to act — {reason}", task_id)
    bump_ledger(pid, "refused")


def escalate(pid: str, task_id: str, agent: str, trigger: str,
             context: dict[str, Any] | None = None) -> None:
    if not _enter_terminal(pid, task_id, {
        "status": "escalated",
        "escalation": {"trigger": trigger, "slaStartedAt": _now(),
                       "context": context or {}, "resolvedBy": None},
    }):
        return
    audit(pid, "escalation", agent, f"escalated to human — {trigger}", task_id)
    # "escalated", not "humanDecisions". At this moment nobody has decided
    # anything — the task has been handed over and is waiting. Counting a
    # handover as a decision would put a number on screen that is not true yet,
    # and the whole point of this ledger is that every figure on it survives
    # being checked.
    bump_ledger(pid, "escalated")


def resolve_escalation(pid: str, task_id: str, actor: str, note: str = "") -> dict[str, Any]:
    """Close an escalation. Only a human calls this.

    Escalations are the one terminal state no agent can clear — that is what
    "human-terminated" means, and it is only true if there is exactly one way
    out and it requires a person. The SLA clock stops here and nowhere else.
    """
    ref = task_ref(pid, task_id)
    snap = ref.get()
    if not snap.exists:
        raise KeyError(f"task {task_id} not found for {pid}")
    data = snap.to_dict() or {}
    esc = data.get("escalation") or {}
    # Already closed is not an error. Two clinicians can be looking at the same
    # queue, and a double-click should say who got there first, not throw.
    if esc.get("resolvedBy"):
        return {"taskId": task_id, "alreadyResolvedBy": esc["resolvedBy"]}
    if data.get("status") != "escalated":
        raise ValueError(f"task {task_id} is '{data.get('status')}', not an open escalation")

    started = esc.get("slaStartedAt")
    elapsed = int((_now() - started).total_seconds()) if started else None
    ref.update({
        "escalation": {**esc, "resolvedBy": actor, "resolvedAt": _now(),
                       "resolutionNote": note, "elapsedSeconds": elapsed},
        "status": "resolved",
    })
    audit(pid, "action", actor, f"escalation closed by {actor}" + (f" — {note}" if note else ""),
          task_id, {"humanResolved": True, "elapsedSeconds": elapsed})
    bump_ledger(pid, "humanDecisions")
    return {"taskId": task_id, "resolvedBy": actor, "elapsedSeconds": elapsed}


def decide_refusal(pid: str, task_id: str, actor: str, option: str) -> dict[str, Any]:
    """A human picks one of the options a refusal handed them.

    The refusal is not overwritten — the question, the options, and the answer
    all stay on the task. Six months later the useful record is not "amlodipine
    was stopped", it is "the fleet would not choose, and this named person did,
    at this time, from these two readings".
    """
    ref = task_ref(pid, task_id)
    snap = ref.get()
    if not snap.exists:
        raise KeyError(f"task {task_id} not found for {pid}")
    data = snap.to_dict() or {}
    ref_data = data.get("refusal") or {}
    if ref_data.get("decidedBy"):
        return {"taskId": task_id, "alreadyDecidedBy": ref_data["decidedBy"]}
    if data.get("status") != "refused":
        raise ValueError(f"task {task_id} is '{data.get('status')}', not an open refusal")
    if option not in (ref_data.get("options") or []):
        raise ValueError("that option was not one of the ones offered")

    ref.update({
        "refusal": {**ref_data, "decidedBy": actor, "decision": option, "decidedAt": _now()},
        "status": "resolved",
    })
    audit(pid, "action", actor, f"{actor} decided: {option}", task_id,
          {"humanDecision": True, "question": ref_data.get("reason")})
    bump_ledger(pid, "humanDecisions")
    return {"taskId": task_id, "decidedBy": actor, "decision": option}


def fail(pid: str, task_id: str, agent: str, err: str) -> None:
    task_ref(pid, task_id).update({"status": "failed", "error": err})
    audit(pid, "action", agent, f"task failed: {err}", task_id)


# --------------------------------------------------------------------------
# autonomy ledger — verifiable counts only, never invented dollars
# --------------------------------------------------------------------------

LedgerField = Literal["autonomous", "escalated", "refused", "humanDecisions",
                      "systemsTouched"]
"""What the ledger counts, and the distinction that matters:

  autonomous      the fleet finished it, no human involved
  escalated       handed to a clinician — waiting, not resolved
  refused         the fleet would not choose; a human was handed the options
  humanDecisions  a named person actually decided or closed something
  systemsTouched  writes to real external systems
"""


def bump_ledger(pid: str, field: LedgerField) -> None:
    db().collection("ledger").document(pid).set(
        {field: firestore.Increment(1), "updatedAt": _now()}, merge=True
    )


def read_ledger(pid: str) -> dict[str, int]:
    snap = db().collection("ledger").document(pid).get()
    d = snap.to_dict() if snap.exists else {}
    return {
        "autonomous": int(d.get("autonomous", 0)),
        "escalated": int(d.get("escalated", 0)),
        "refused": int(d.get("refused", 0)),
        "humanDecisions": int(d.get("humanDecisions", 0)),
        "systemsTouched": int(d.get("systemsTouched", 0)),
    }
