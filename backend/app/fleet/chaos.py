"""Chaos panel — the Failure Drill.

We hand this to the judge. They pick which agent dies and when. The point is
that recovery is *infrastructure*, not a scripted animation:

  kill  → the container process exits
  detect→ supervisor sees the heartbeat go stale, writes AGENT_DOWN
  recover→ Pub/Sub redelivers the message; Cloud Run has a fresh container
  replay→ the ledger skips completed steps, runs only what's left

Nothing here fakes anything. ``os._exit(1)`` is a real, ungraceful death.
"""
from __future__ import annotations

import os
import threading

from .ledger import audit


def kill_process(agent: str, pid: str | None = None, delay_ms: int = 250) -> dict:
    """Terminate this worker ungracefully, after flushing one audit line."""
    if pid:
        audit(pid, "AGENT_DOWN", agent,
              f"chaos: {agent} process killed by operator (drill)", None,
              {"drill": True})

    def _die() -> None:
        os._exit(1)   # no cleanup, no atexit, no graceful shutdown — a real crash

    threading.Timer(delay_ms / 1000.0, _die).start()
    return {"killed": agent, "in_ms": delay_ms,
            "note": "process will exit; Pub/Sub redelivery + ledger replay will recover the task"}
