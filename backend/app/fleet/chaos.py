"""Chaos panel — the Failure Drill.

We hand this to the judge. They choose which agent dies. The point is that
recovery is *infrastructure*, not choreography:

  kill   → the container process exits, ungracefully
  detect → supervisor sees the heartbeat go stale, writes AGENT_DOWN
  recover→ Pub/Sub redelivers the unacked message; Cloud Run has a fresh container
  replay → the ledger skips completed steps and runs only what is left

Two ways to pull the trigger:

  kill_now()  — terminate immediately. Honest, but on Cloud Run the request may
                land on an instance that is not the one doing the work, so it is
                unreliable as a *demo* instrument.

  arm()       — mark an agent for death on its next task. The worker kills itself
                from inside the step it is executing. Deterministic, lands in the
                window every time, and is still a genuine ungraceful exit — the
                process does not get to finish, flush, or ack.

Nothing here simulates a failure. ``os._exit(1)`` skips atexit handlers, buffered
writes and graceful shutdown. It is exactly as violent as a real crash.

Note on scaling: the arm lives in Firestore, not in process memory, so it works
regardless of how many Cloud Run instances are up — whichever worker picks up
the next task for that agent consumes it and dies. Cloud Run's max-instances was
held low while kills were hand-timed, to raise the odds of hitting the busy
container. Arming removed that constraint entirely.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

from .ledger import audit, db

log = logging.getLogger("vitahome.chaos")

_ARMED_DOC = ("chaos", "armed")


def _doc():
    return db().collection(_ARMED_DOC[0]).document(_ARMED_DOC[1])


def arm(agent: str, patient_id: str | None = None,
        step: str | None = None) -> dict[str, Any]:
    """Mark ``agent`` to die inside a specific step. Shared across instances.

    ``step`` matters more than it looks. Without it the arm fires on whichever
    step comes first — which for the Scheduler is ``resolve_provider``, step one
    of three. The task then dies before anything has completed, and the replay
    starts from scratch with nothing to skip.

    That still demonstrates redelivery and no-duplicate booking, but it silently
    fails to demonstrate the thing the drill exists for: that work already done
    is *not repeated*. Three consecutive drill runs looked perfect and never
    once produced a skip, because the kill kept landing on step one.

    Targeting step two means step one is committed to the ledger before the
    process dies, so the replay has something real to skip.
    """
    _doc().set({
        "agent": agent,
        "step": step,
        "armedAt": datetime.now(timezone.utc),
        "patientId": patient_id,
    })
    log.warning("chaos armed for agent=%s step=%s", agent, step or "<first>")
    where = f"inside step '{step}'" if step else "inside its next step"
    if patient_id:
        audit(patient_id, "action", agent,
              f"chaos armed — {agent} will be killed {where}", None,
              {"drill": True, "step": step})
    return {"armed": agent, "step": step,
            "note": f"the next task this agent picks up will die {where}"}


def disarm() -> dict[str, Any]:
    _doc().delete()
    return {"armed": None}


def armed() -> dict[str, Any] | None:
    try:
        snap = _doc().get()
        return (snap.to_dict() or {}) if snap.exists else None
    except Exception:  # noqa: BLE001 — chaos must never break the fleet
        return None


def armed_agent() -> str | None:
    return (armed() or {}).get("agent")


def consume_if_armed(agent: str, patient_id: str, task_id: str, step_name: str) -> bool:
    """If this agent is armed for this step, record it, clear the arm, and die.

    Returns False otherwise — including when the agent is armed but for a later
    step, which is how earlier steps get to complete and be skipped on replay.
    """
    a = armed() or {}
    if a.get("agent") != agent:
        return False
    target = a.get("step")
    if target and target != step_name:
        return False
    try:
        _doc().delete()                      # one-shot: never a kill loop
        audit(patient_id, "AGENT_DOWN", agent,
              f"killed mid-step '{step_name}' — process exiting without ack", task_id,
              {"drill": True, "step": step_name})
    except Exception:  # noqa: BLE001
        pass
    log.error("CHAOS: %s dying inside step '%s' of task %s", agent, step_name, task_id)
    os._exit(1)                              # no cleanup, no ack, no mercy


def kill_now(agent: str, patient_id: str | None = None, delay_ms: int = 250) -> dict[str, Any]:
    """Terminate this worker immediately (whichever instance serves the request)."""
    if patient_id:
        audit(patient_id, "AGENT_DOWN", agent,
              f"chaos: {agent} process killed by operator", None, {"drill": True})

    threading.Timer(delay_ms / 1000.0, lambda: os._exit(1)).start()
    return {"killed": agent, "in_ms": delay_ms,
            "note": "process exiting; Pub/Sub redelivery + ledger replay will recover the task"}
