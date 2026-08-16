"""VitaHome gateway.

Hosts:
  * the synchronous Parser (the ~1s photo→plan moment the demo opens on)
  * the six agent push endpoints (Pub/Sub delivers here)
  * the fleet registry (A2A agent cards)
  * the chaos panel the judges drive
  * SSE audit streams the console renders

One service, decoupled contracts: agents communicate through Pub/Sub messages
and Firestore task documents, never direct function calls. Extracting any agent
to its own Cloud Run service is a routing change, not a refactor.
"""
from __future__ import annotations

import base64
import json
import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config import settings
from ..fleet import chaos, ledger, registry, supervisor
from ..integrations import fhir

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("vitahome")

app = FastAPI(title="VitaHome Fleet", version=registry.FLEET_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

AGENT_NAMES = ["parser", "reconciler", "scheduler", "pharmacist",
               "watchman", "coach", "escalator"]


# ---------------------------------------------------------------- health ----

@app.get("/health")
@app.get("/healthz")
def health():
    return {"ok": True, "service": "vitahome-gateway",
            "version": registry.FLEET_VERSION, "region": settings.region}


@app.get("/health/deep")
def health_deep():
    """Proves the whole substrate is live — used in the demo to show real infra."""
    return {"ok": True, "fhir": fhir.ping(),
            "project": settings.gcp_project, "fhirStore": settings.hc_fhir_store}


# -------------------------------------------------------------- registry ----

@app.get("/registry")
def get_registry():
    """A2A agent cards. The Fleet track's 'agent registry' requirement, at a URL."""
    return registry.registry()


@app.get("/registry/{agent}")
def get_agent_card(agent: str):
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    return registry.agent_card(agent)


# ------------------------------------------------------------- the fleet ----

class CaptureRequest(BaseModel):
    patientId: str = "p_hero"
    documentText: str | None = None      # dev path; image path added day 5


@app.post("/capture")
def capture(req: CaptureRequest):
    """Synchronous parse — the demo's opening beat. Day 5 makes this multimodal."""
    return {"status": "stub", "patientId": req.patientId,
            "note": "Parser lands day 5 (see docs/BUILD-PLAN.md §5.4)"}


@app.get("/patient/{pid}/plan")
def get_plan(pid: str):
    snap = ledger.db().collection("patients").document(pid).get()
    if not snap.exists:
        raise HTTPException(404, "no such patient")
    return snap.to_dict()


@app.get("/patient/{pid}/ledger")
def get_ledger(pid: str):
    """Autonomy Ledger — verifiable counts only, never invented dollars."""
    return ledger.read_ledger(pid)


@app.get("/patient/{pid}/tasks")
def get_tasks(pid: str):
    tasks = (ledger.db().collection("patients").document(pid)
             .collection("tasks").order_by("createdAt").limit(100).stream())
    return {"tasks": [t.to_dict() for t in tasks]}


@app.get("/patient/{pid}/audit")
def get_audit(pid: str, limit: int = 200):
    from google.cloud import firestore as fs
    rows = (ledger.db().collection("patients").document(pid).collection("audit")
            .order_by("at", direction=fs.Query.DESCENDING).limit(limit).stream())
    return {"audit": [r.to_dict() for r in rows]}


# ------------------------------------------------- agent push endpoints ----

def _decode_push(envelope: dict) -> dict:
    """Pub/Sub push envelope → our message body."""
    msg = envelope.get("message", {})
    raw = base64.b64decode(msg.get("data", "")).decode() if msg.get("data") else "{}"
    return json.loads(raw)


@app.post("/agents/{agent}")
async def agent_endpoint(agent: str, request: Request):
    """One endpoint per agent; Pub/Sub push subscriptions target these.

    Returning 200 acks the message. Returning 5xx (or dying) leaves it unacked,
    which is exactly what makes the Failure Drill recover: Pub/Sub redelivers.
    """
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    envelope = await request.json()
    body = _decode_push(envelope) if "message" in envelope else envelope
    log.info("agent=%s task=%s attempt=%s", agent, body.get("taskId"), body.get("attempt"))
    # Day 6-11 wire the real handlers here.
    return {"status": "stub", "agent": agent, "received": body}


# ------------------------------------------------------------ the drill ----

@app.post("/chaos/kill")
def chaos_kill(agent: str = "scheduler", patientId: str | None = None):
    """The judge picks the agent and the moment. This really kills the process."""
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    return chaos.kill_process(agent, patientId)


@app.post("/supervisor/scan")
def supervisor_scan():
    """Detect stale leases and write AGENT_DOWN. Cloud Scheduler calls this every 5s."""
    return {"flagged": supervisor.scan_stale()}


# --------------------------------------------------------------- console ----

@app.get("/console/fleets")
def console_fleets(limit: int = 250):
    pts = ledger.db().collection("patients").limit(limit).stream()
    out = []
    for p in pts:
        d = p.to_dict() or {}
        out.append({"id": p.id,
                    "name": (d.get("profile") or {}).get("name", p.id),
                    "state": d.get("fleetState", "idle")})
    return {"fleets": out, "count": len(out)}


def run() -> None:
    uvicorn.run("app.gateway.main:app", host="0.0.0.0", port=settings.port,
                log_level=settings.log_level.lower())


if __name__ == "__main__":
    run()
