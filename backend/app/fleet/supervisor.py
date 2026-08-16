"""Supervisor — detects and narrates. It deliberately does NOT respawn.

Cloud Run restarts containers; Pub/Sub redelivers work. Those are the recovery
mechanisms and they are battle-tested. Writing our own respawn loop on top
would be theatre and would fight the platform.

What the supervisor adds is *observability*: it notices a lease has gone stale
and writes the AGENT_DOWN event that the console renders as the red gap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from ..config import settings
from .ledger import audit, db


def scan_stale(grace_seconds: int | None = None) -> list[dict]:
    """Find leased tasks whose heartbeat has gone stale and flag them once."""
    grace = grace_seconds or (settings.heartbeat_seconds * 3)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=grace)
    flagged: list[dict] = []

    tasks = (
        db().collection_group("tasks")
        .where(filter=firestore.FieldFilter("status", "==", "leased"))
        .limit(100).stream()
    )
    for snap in tasks:
        t = snap.to_dict()
        hb = t.get("heartbeatAt")
        if hb is None or t.get("downFlagged"):
            continue
        if hb.replace(tzinfo=timezone.utc) < cutoff:
            pid = snap.reference.parent.parent.id
            gap = (datetime.now(timezone.utc) - hb.replace(tzinfo=timezone.utc)).total_seconds()
            audit(pid, "AGENT_DOWN", t.get("agent", "?"),
                  f"no heartbeat for {gap:.1f}s — worker presumed dead",
                  t.get("taskId"), {"gapSeconds": round(gap, 1)})
            snap.reference.update({"downFlagged": True})
            flagged.append({"patient": pid, "task": t.get("taskId"),
                            "agent": t.get("agent"), "gapSeconds": round(gap, 1)})
    return flagged
