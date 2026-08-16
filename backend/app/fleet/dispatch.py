"""Fan-out — the only way work reaches an agent.

Agents are addressed by Pub/Sub attribute, not by function call. Each agent has
its own push subscription filtered on ``agent``. That is what makes the fleet
decoupled: moving an agent to its own Cloud Run service changes a push endpoint,
not a line of application code.

Messages carry FHIR/Firestore *references* only — never PHI. Agents fetch inside
their own IAM scope. That is the compliance-aware data handling story.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from google.cloud import pubsub_v1

from ..config import settings
from . import ledger

log = logging.getLogger("vitahome.dispatch")

_publisher: pubsub_v1.PublisherClient | None = None


def publisher() -> pubsub_v1.PublisherClient:
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def topic_path(topic: str) -> str:
    return publisher().topic_path(settings.gcp_project, topic)


def dispatch(pid: str, agent: str, instruction_id: str | None = None,
             payload: dict[str, Any] | None = None) -> str:
    """Create a task and hand it to the fleet. Returns the task id."""
    task_id = ledger.create_task(pid, agent, instruction_id, payload)
    body = {
        "taskId": task_id,
        "patientRef": f"patients/{pid}",
        "patientId": pid,
        "agent": agent,
        "instructionId": instruction_id,
    }
    publisher().publish(
        topic_path(settings.topic_fleet_work),
        json.dumps(body).encode(),
        agent=agent,                    # subscription filter key
        patientId=pid,
    ).result(timeout=15)
    log.info("dispatched agent=%s task=%s", agent, task_id)
    return task_id
