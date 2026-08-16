"""Async runtime — the supervised execution wrapper every agent runs inside.

Responsibilities:
  * claim the task (records redelivery when a previous worker died)
  * keep a heartbeat alive in a background thread while work happens
  * translate outcomes into ledger terminal states
  * re-raise on failure so Pub/Sub does NOT ack — that redelivery is our recovery

The agent body itself never touches lifecycle concerns. It just calls
``ledger.run_step`` for each side effect and returns.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from typing import Any, Callable

from ..config import settings
from . import ledger

log = logging.getLogger("vitahome.runtime")


def _worker_id() -> str:
    """A name unique to THIS process.

    Cloud Run gives every container the hostname ``localhost`` and PID 1, so
    hostname+pid is identical across instances — which would make the audit log
    show the same worker before and after a kill and quietly undermine the
    thing the drill is trying to prove. The random suffix is minted once at
    import, so a new worker is visibly a new worker.
    """
    rev = os.getenv("K_REVISION") or socket.gethostname()
    return f"{rev.rsplit('-', 2)[-1] if '-' in rev else rev}·{uuid.uuid4().hex[:6]}"


WORKER_ID = _worker_id()

AgentBody = Callable[[str, str, dict[str, Any]], str]
"""(patient_id, task_id, task_data) -> human-readable completion summary"""


class Refusal(Exception):
    """Raised by an agent that will not act on an ambiguous instruction.

    This is not an error. It is the product thesis: the fleet executes the
    mechanical and hands every clinical judgement to a licensed human.
    """

    def __init__(self, reason: str, options: list[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.options = options or []


class Escalation(Exception):
    """Raised when a human clinician must be paged."""

    def __init__(self, trigger: str, context: dict[str, Any] | None = None):
        super().__init__(trigger)
        self.trigger = trigger
        self.context = context or {}


class _Heartbeat:
    """Keeps the lease fresh while the agent works; stops on exit.

    If the process is killed, this thread dies with it — the heartbeat goes
    stale and the supervisor notices. That staleness is the signal the console
    renders as the red gap.
    """

    def __init__(self, pid: str, task_id: str):
        self.pid, self.task_id = pid, task_id
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def __enter__(self) -> "_Heartbeat":
        def _loop() -> None:
            while not self._stop.wait(settings.heartbeat_seconds):
                try:
                    ledger.beat(self.pid, self.task_id)
                except Exception:  # noqa: BLE001 — never let liveness kill the work
                    log.warning("heartbeat failed", exc_info=True)
        self._t = threading.Thread(target=_loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()


def run_task(agent: str, pid: str, task_id: str, body: AgentBody) -> dict[str, Any]:
    """Execute one agent task under full lifecycle supervision."""
    # A redelivery of work that already finished is a no-op: ack it and stop.
    #
    # This has to happen BEFORE claiming, because claim() unconditionally sets
    # the task back to "leased" and bumps its attempt counter. A finished task
    # redelivered enough times therefore walked its own counter past the poison
    # ceiling and dead-lettered itself — arriving in the clinician's queue
    # labelled "failed 6 times" with all three of its steps sitting there
    # completed. Ten fleets did exactly that during a 200-task burst.
    #
    # At-least-once delivery means duplicates are expected, not exceptional. The
    # step ledger already makes the side effects safe; this makes the lifecycle
    # safe too.
    settled = ledger.peek(pid, task_id)
    if settled and settled.get("status") in ledger.SETTLED:
        status = settled["status"]
        ledger.audit(pid, "skip", agent,
                     f"redelivered after the task was already {status} — acked, nothing re-run",
                     task_id, {"duplicateDelivery": True})
        return {"status": f"already_{status}", "attempt": settled.get("attempt")}

    task = ledger.claim(pid, task_id, WORKER_ID)
    attempt = task.get("attempt", 1)
    log.info("agent=%s pid=%s task=%s attempt=%s worker=%s",
             agent, pid, task_id, attempt, WORKER_ID)

    # Poison-message guard. Redelivery is our recovery mechanism, but a task
    # that fails deterministically would retry forever and starve the fleet.
    # After max_attempts we dead-letter it to the human queue and ACK, so the
    # loop stops. Retries recover from crashes; they must not mask real bugs.
    if attempt > settings.max_attempts:
        ledger.escalate(
            pid, task_id, agent,
            f"failed {attempt - 1} times — dead-lettered for human review",
            {"deadLetter": True, "lastError": task.get("error")},
        )
        log.error("agent=%s task=%s dead-lettered after %s attempts", agent, task_id, attempt - 1)
        return {"status": "dead_letter", "attempt": attempt}

    try:
        with _Heartbeat(pid, task_id):
            summary = body(pid, task_id, task)
        ledger.complete(pid, task_id, agent, summary)
        return {"status": "done", "attempt": attempt, "summary": summary}

    except Refusal as r:
        ledger.refuse(pid, task_id, agent, r.reason, r.options)
        return {"status": "refused", "attempt": attempt, "reason": r.reason}

    except Escalation as e:
        ledger.escalate(pid, task_id, agent, e.trigger, e.context)
        return {"status": "escalated", "attempt": attempt, "trigger": e.trigger}

    except Exception as e:  # noqa: BLE001
        log.exception("agent=%s task=%s failed", agent, task_id)
        ledger.fail(pid, task_id, agent, str(e)[:300])
        raise      # 5xx → Pub/Sub will redeliver → the ledger replays
