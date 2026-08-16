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
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..agents import parser as parser_agent
from ..agents import reconciler as reconciler_agent
from ..agents import scheduler as scheduler_agent
from ..config import settings
from ..fleet import chaos, dispatch, ledger, registry, runtime, supervisor
from ..integrations import fhir, gemini
from ..sim import hero_patient

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
    return {"ok": True, "fhir": fhir.ping(), "gemini": gemini.ping(),
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
    documentText: str | None = None


@app.post("/capture")
def capture(req: CaptureRequest):
    """Parse a document supplied as text. See /capture/photo for the image path."""
    try:
        return parser_agent.parse(req.patientId, text=req.documentText)
    except gemini.ModelError as e:
        raise HTTPException(502, f"parse failed: {e}") from e


@app.post("/capture/photo")
async def capture_photo(file: UploadFile = File(...), patientId: str = Form("p_hero")):
    """The demo's opening beat: photograph the discharge summary, get a plan.

    Synchronous, unlike the rest of the fleet — a human is standing there holding
    a phone, and the ~1s wait is the product. Everything downstream of this is
    async over Pub/Sub.
    """
    if file.content_type not in {"image/jpeg", "image/png", "image/webp", "image/heic"}:
        raise HTTPException(415, f"unsupported image type: {file.content_type}")
    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(413, "image larger than 12 MB")
    try:
        return parser_agent.parse(patientId, image=data, mime_type=file.content_type)
    except gemini.ModelError as e:
        raise HTTPException(502, f"parse failed: {e}") from e


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
def get_tasks(pid: str, limit: int = 60):
    """Sorted in Python, not Firestore — no composite index to provision, and
    the collection is bounded per patient."""
    snaps = (ledger.db().collection("patients").document(pid)
             .collection("tasks").limit(limit).stream())
    tasks = [t.to_dict() for t in snaps]
    tasks.sort(key=lambda t: t.get("createdAt") or 0)
    return {"tasks": tasks, "count": len(tasks)}


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


# Agent bodies. Each is a pure function of (patient, task) that calls
# ledger.run_step for every side effect — lifecycle is handled by the runtime.
HANDLERS = {
    "scheduler": scheduler_agent.body,
    "reconciler": reconciler_agent.body,
}


@app.post("/agents/{agent}")
async def agent_endpoint(agent: str, request: Request):
    """One endpoint per agent; Pub/Sub push subscriptions target these.

    Returning 200 acks the message. Returning 5xx — or dying mid-request —
    leaves it unacked, and that redelivery is exactly how the Failure Drill
    recovers. We do not catch-and-swallow: failures must propagate.
    """
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")

    envelope = await request.json()
    body = _decode_push(envelope) if "message" in envelope else envelope
    pid, task_id = body.get("patientId"), body.get("taskId")
    if not pid or not task_id:
        raise HTTPException(400, "patientId and taskId required")

    handler = HANDLERS.get(agent)
    if handler is None:
        ledger.audit(pid, "action", agent, f"{agent} not yet implemented — task parked", task_id)
        return {"status": "unimplemented", "agent": agent, "taskId": task_id}

    return runtime.run_task(agent, pid, task_id, handler)


# ------------------------------------------------------------------ demo ----

@app.post("/demo/seed")
def demo_seed():
    """Create the synthetic hero patient in FHIR + Firestore. Idempotent."""
    return hero_patient.seed()


class DispatchRequest(BaseModel):
    patientId: str = "p_hero"
    agent: str = "scheduler"
    instructionId: str | None = None
    payload: dict = {}


@app.post("/demo/dispatch")
def demo_dispatch(req: DispatchRequest):
    """Hand a task to the fleet over Pub/Sub."""
    if req.agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    task_id = dispatch.dispatch(req.patientId, req.agent, req.instructionId, req.payload)
    return {"taskId": task_id, "agent": req.agent, "patientId": req.patientId}


@app.post("/demo/book-followups")
def demo_book_followups(patientId: str = "p_hero"):
    """Dispatch a Scheduler task for every follow-up on the care plan."""
    snap = ledger.db().collection("patients").document(patientId).get()
    if not snap.exists:
        raise HTTPException(404, "seed the patient first: POST /demo/seed")
    d = snap.to_dict() or {}
    fhir_pid = (d.get("profile") or {}).get("fhirPatientId")
    out = []
    for ins in (d.get("carePlan") or {}).get("instructions", []):
        if ins.get("type") == "followup":
            tid = dispatch.dispatch(patientId, "scheduler", ins["id"], {
                "specialty": ins.get("specialty"),
                "daysOut": ins.get("daysOut", 7),
                "fhirPatientId": fhir_pid,
            })
            out.append({"instruction": ins["id"], "taskId": tid,
                        "specialty": ins.get("specialty")})
    return {"dispatched": out, "count": len(out)}


# ------------------------------------------------------------ the drill ----

@app.post("/chaos/arm")
def chaos_arm(agent: str = "scheduler", patientId: str | None = None):
    """Arm an agent to die inside its next step.

    Deterministic and still a genuine ungraceful exit — the worker kills itself
    mid-step, before the side effect, with the Pub/Sub message unacked.
    """
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    return chaos.arm(agent, patientId)


@app.post("/chaos/disarm")
def chaos_disarm():
    return chaos.disarm()


@app.get("/chaos/status")
def chaos_status():
    return {"armed": chaos.armed_agent()}


@app.post("/chaos/kill")
def chaos_kill(agent: str = "scheduler", patientId: str | None = None):
    """Kill immediately, whichever instance serves this request."""
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    return chaos.kill_now(agent, patientId)


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
