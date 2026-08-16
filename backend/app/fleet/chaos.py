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


def arm(agent: str, patient_id: str | None = None) -> dict[str, Any]:
    """Mark ``agent`` to die inside its next step. Shared across instances."""
    _doc().set({
        "agent": agent,
        "armedAt": datetime.now(timezone.utc),
        "patientId": patient_id,
    })
    log.warning("chaos armed for agent=%s", agent)
    if patient_id:
        audit(patient_id, "action", agent,
              f"chaos armed — {agent} will be killed inside its next step", None,
              {"drill": True})
    return {"armed": agent,
            "note": "the next task this agent picks up will die mid-step"}


def disarm() -> dict[str, Any]:
    _doc().delete()
    return {"armed": None}


def armed_agent() -> str | None:
    try:
        snap = _doc().get()
        return (snap.to_dict() or {}).get("agent") if snap.exists else None
    except Exception:  # noqa: BLE001 — chaos must never break the fleet
        return None


def consume_if_armed(agent: str, patient_id: str, task_id: str, step_name: str) -> bool:
    """If this agent is armed, record it, clear the arm, and die. Returns False otherwise."""
    if armed_agent() != agent:
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
