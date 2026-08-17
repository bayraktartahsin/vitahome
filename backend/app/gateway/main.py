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
import threading
import time

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..agents import coach as coach_agent
from ..agents import escalator as escalator_agent
from ..agents import parser as parser_agent
from ..agents import pharmacist as pharmacist_agent
from ..agents import reconciler as reconciler_agent
from ..agents import scheduler as scheduler_agent
from ..agents import watchman as watchman_agent
from ..compliance import redact
from ..config import settings
from ..fleet import chaos, dispatch, ledger, registry, runtime, supervisor
from ..integrations import fhir, gemini
from ..sim import cohort, hero_patient, vitals

from google.cloud import firestore  # noqa: E402  — used by the console queries

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("vitahome")

# Installed before any agent runs. PHI is not supposed to reach a log line —
# this is the layer that catches the day that assumption is wrong.
redact.install()

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

class ScanRequest(BaseModel):
    lines: list[str] = []
    minutes: int = 30


@app.post("/compliance/scan")
def compliance_scan(req: ScanRequest):
    """Audit log output for PHI that should never have been written.

    The primary control is structural — agents log references, not clinical
    content — and this is what makes that claim falsifiable rather than a
    promise in a README. Pass log lines directly, or leave them empty and the
    gateway reads its own recent Cloud Logging entries.
    """
    lines = req.lines
    if not lines:
        lines = _recent_log_lines(req.minutes)
    if not lines:
        return {"clean": True, "findings": [], "linesScanned": 0,
                "note": "no log lines available to scan"}
    try:
        return {**redact.scan(lines), "redactionsApplied": redact.redaction_counts()}
    except gemini.ModelError as e:
        raise HTTPException(502, f"scan failed: {e}") from e


def _recent_log_lines(minutes: int, limit: int = 120) -> list[str]:
    """Pull this service's own recent log entries."""
    try:
        from google.cloud import logging as gcl
    except ImportError:
        return []
    try:
        client = gcl.Client(project=settings.gcp_project)
        flt = (f'resource.type="cloud_run_revision" '
               f'resource.labels.service_name="vitahome-gateway" '
               f'timestamp>="{_minutes_ago(minutes)}"')
        out = []
        for entry in client.list_entries(filter_=flt, order_by=gcl.DESCENDING,
                                         max_results=limit):
            p = entry.payload
            out.append(p if isinstance(p, str) else str(p))
        return out
    except Exception as e:  # noqa: BLE001 — an audit tool must not take the service down
        log.warning("could not read logs: %s", e)
        return []


def _minutes_ago(m: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(minutes=m)) \
        .isoformat(timespec="seconds").replace("+00:00", "Z")


@app.get("/compliance/redactions")
def compliance_redactions():
    """What the deterministic filter has scrubbed since this instance started."""
    return {"redactions": redact.redaction_counts(),
            "note": "defence in depth — PHI is not supposed to reach a log line at all"}


@app.get("/usage")
def usage():
    """What the model calls actually cost, in tokens.

    Counted rather than estimated, for the same reason the Autonomy Ledger
    counts actions instead of guessing at savings: a number nobody can check is
    worth less than no number at all.
    """
    return gemini.usage_report()


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


class HumanAction(BaseModel):
    actor: str = "Dr. Chen"
    note: str = ""
    option: str | None = None


@app.post("/patient/{pid}/task/{task_id}/resolve")
def resolve_escalation(pid: str, task_id: str, req: HumanAction):
    """Close an escalation. The only exit from a human-terminated task."""
    try:
        return ledger.resolve_escalation(pid, task_id, req.actor, req.note)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/patient/{pid}/task/{task_id}/decide")
def decide_refusal(pid: str, task_id: str, req: HumanAction):
    """Answer a refusal by choosing one of the options it offered."""
    if not req.option:
        raise HTTPException(400, "option is required")
    try:
        return ledger.decide_refusal(pid, task_id, req.actor, req.option)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/patient/{pid}/exceptions")
def get_exceptions(pid: str):
    """Everything waiting on a person, worst SLA first.

    Sorted by how long it has been waiting against its own deadline — not by
    arrival. A queue ordered by arrival time is a queue that lets the urgent
    thing sit behind the routine one.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Filter in Firestore, not in Python. This endpoint is polled continuously
    # by the console; reading every task document and discarding the 98% that
    # are already done meant ~200 billed reads per poll, per open tab, forever.
    # The single-field index on `status` exists automatically.
    snaps = (ledger.db().collection("patients").document(pid)
             .collection("tasks")
             .where(filter=firestore.FieldFilter("status", "in", ["refused", "escalated"]))
             .limit(50).stream())
    out = []
    for s in snaps:
        t = s.to_dict() or {}
        esc, ref = t.get("escalation") or {}, t.get("refusal") or {}
        # Everything the Escalator decided lives under escalation.context —
        # ledger.escalate stores the agent's payload there verbatim rather than
        # spreading it, so the ledger stays agnostic about what an agent
        # attaches. Flatten it here, at the API boundary, for the console.
        ctx = esc.get("context") or {}
        started = esc.get("slaStartedAt") or ref.get("at")
        sla = int(ctx.get("slaMinutes") or 0)
        waited = int((now - started).total_seconds()) if started else 0
        out.append({
            "taskId": t.get("taskId"), "agent": t.get("agent"), "kind": t.get("status"),
            "question": ref.get("reason") or esc.get("trigger"),
            "options": ref.get("options") or [],
            "urgency": ctx.get("urgency"),
            "rationale": ctx.get("rationale"),
            "argumentsAgainst": ctx.get("argumentsAgainst"),
            "hardOverride": bool(ctx.get("hardOverride")),
            "deadLetter": bool(ctx.get("deadLetter")),
            "waitedSeconds": waited,
            "slaSeconds": sla * 60,
            "breached": bool(sla) and waited > sla * 60,
        })
    # Breached first, then closest to breaching. Refusals have no SLA, so they
    # sort by how long they have waited — an unanswered question is not free.
    out.sort(key=lambda r: (not r["breached"],
                            -(r["waitedSeconds"] / r["slaSeconds"]) if r["slaSeconds"]
                            else -r["waitedSeconds"] / 3600))
    return {"exceptions": out, "count": len(out),
            "breached": sum(1 for r in out if r["breached"])}


@app.get("/patient/{pid}/checkin/audio")
def checkin_audio(pid: str):
    """Read today's check-in question aloud.

    Synthesised on demand, not at check-in time: a question nobody plays costs
    nothing, and the text is the durable artefact either way. If speech is
    unavailable this returns 503 with the reason — the caller shows the text,
    which is what it was showing anyway.
    """
    doc = ledger.db().collection("patients").document(pid).get().to_dict() or {}
    q = (doc.get("openCheckIn") or {}).get("question")
    if not q:
        raise HTTPException(404, "no open check-in for this patient")
    try:
        pcm, mime = gemini.speak(q)
    except gemini.VoiceUnavailable as e:
        raise HTTPException(503, f"voice unavailable — showing text instead: {e}") from e
    return Response(content=gemini.pcm_to_wav(pcm, mime), media_type="audio/wav",
                    headers={"Cache-Control": "no-store"})


class CheckInAnswer(BaseModel):
    answer: str


@app.post("/patient/{pid}/checkin/answer")
def answer_checkin(pid: str, req: CheckInAnswer):
    """The family answers today's question.

    The answer does not come back to the Coach. It goes to the Watchman, which
    is the component that knows this document's red flags — the Coach asks, it
    does not judge. That keeps a single place responsible for deciding whether
    something reported at home matters.
    """
    ref = ledger.db().collection("patients").document(pid)
    doc = ref.get().to_dict() or {}
    open_q = doc.get("openCheckIn") or {}
    if not open_q or open_q.get("answer"):
        raise HTTPException(409, "no open check-in for this patient")

    ref.set({"openCheckIn": {**open_q, "answer": req.answer}}, merge=True)
    task_id = dispatch.dispatch(pid, "watchman", None, {
        "observation": f"Asked: {open_q['question']}  Answered: {req.answer}",
        "context": f"daily check-in about {open_q.get('about')}",
        "source": "coach check-in",
    })
    ledger.audit(pid, "action", "coach",
                 f"answer received on {open_q.get('about')} — routed to the Watchman", task_id)
    return {"routedTo": "watchman", "taskId": task_id, "about": open_q.get("about")}


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
    "pharmacist": pharmacist_agent.body,
    "watchman": watchman_agent.body,
    "coach": coach_agent.body,
    "escalator": escalator_agent.body,
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

    # run_task is entirely blocking — FHIR round trips, Gemini calls, Firestore
    # writes, and the drill's deliberate sleep. Calling it directly from an
    # async handler blocks the event loop for the whole task, so the instance
    # serves nothing else until the agent finishes.
    #
    # Found by watching the console go dark for 165 seconds during a 200-task
    # burst: the dashboard was not slow, it was never scheduled. Handing the
    # work to the threadpool keeps the loop free to answer everything else.
    return await run_in_threadpool(runtime.run_task, agent, pid, task_id, handler)


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


@app.post("/demo/reset")
def demo_reset(patientId: str = "p_hero"):
    """Clear this patient's tasks, audit trail and counters.

    For rehearsals. The demo shows an Autonomy Ledger and an audit stream, and
    both are worthless on camera if they still carry yesterday's practice runs.

    Scoped to one patient and deliberately not exposed anywhere in the UI: the
    audit trail is append-only by design, and the one thing that may erase it is
    an explicit operator action against a named demo fleet.
    """
    pdoc = ledger.db().collection("patients").document(patientId)
    removed = {"tasks": 0, "audit": 0}
    for coll in ("tasks", "audit"):
        # Batched deletes: a patient with a few hundred audit rows would
        # otherwise be a few hundred round trips.
        while True:
            batch = ledger.db().batch()
            docs = list(pdoc.collection(coll).limit(400).stream())
            if not docs:
                break
            for d in docs:
                batch.delete(d.reference)
            batch.commit()
            removed[coll] += len(docs)
    ledger.db().collection("ledger").document(patientId).delete()
    pdoc.set({"openConflicts": [], "fleetState": "idle"}, merge=True)
    chaos.disarm()
    return {"reset": patientId, "removed": removed, "ledger": ledger.read_ledger(patientId)}


@app.get("/demo/scenarios")
def demo_scenarios():
    """The two home-monitoring scenarios, labelled with what each is meant to show."""
    return {"scenarios": [vitals.scenario(k) for k in vitals.SCENARIOS],
            "source": "simulated home monitor"}


@app.post("/demo/observe")
def demo_observe(scenario: str = "chest_pain", patientId: str = "p_hero"):
    """Send a home-monitoring report into the fleet.

    Goes to the Watchman, which records it and decides whether it matches this
    patient's own red flags. The Watchman never pages anyone — if something
    matches, it hands off to the Escalator, and that agent decides.
    """
    try:
        sc = vitals.scenario(scenario)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    task_id = dispatch.dispatch(patientId, "watchman", None, {
        "observation": sc["observation"], "context": sc["context"],
        "scenario": scenario, "source": "simulated home monitor",
    })
    return {"taskId": task_id, "scenario": scenario, "expect": sc["expect"],
            "agent": "watchman"}


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
def chaos_arm(agent: str = "scheduler", patientId: str | None = None,
              step: str | None = "fhir_appointment"):
    """Arm an agent to die inside a named step.

    Deterministic and still a genuine ungraceful exit — the worker kills itself
    mid-step, before the side effect, with the Pub/Sub message unacked.

    The step defaults to the Scheduler's SECOND step on purpose. Killing on the
    first one proves redelivery but leaves nothing completed, so the replay has
    nothing to skip — and "already-done work is not repeated" is the whole point
    of the exercise. Pass step= for a different agent, or step=  (empty) to die
    on whichever step comes first.
    """
    if agent not in AGENT_NAMES:
        raise HTTPException(404, "unknown agent")
    return chaos.arm(agent, patientId, step or None)


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

# The grid polls every couple of seconds and costs ~450 Firestore reads a call.
# One recomputation per window, shared by every poller, is plenty for a
# dashboard — and it keeps the burst screen cheap while the fleet is busy.
_FLEETS_TTL = 2.0
_fleets_cache: dict[str, Any] = {"at": 0.0, "data": None, "limit": 0}
_fleets_lock = threading.Lock()


@app.get("/console/fleets")
def console_fleets(limit: int = 250):
    now = time.monotonic()
    with _fleets_lock:
        if (_fleets_cache["data"] is not None
                and _fleets_cache["limit"] == limit
                and now - _fleets_cache["at"] < _FLEETS_TTL):
            return _fleets_cache["data"]
    data = _compute_fleets(limit)
    with _fleets_lock:
        _fleets_cache.update({"at": time.monotonic(), "data": data, "limit": limit})
    return data


def _compute_fleets(limit: int):
    """Every fleet, with state derived from its actual counters.

    Two queries for the whole grid — the patient documents and the ledger
    collection — rather than a subcollection scan per patient, which at two
    hundred fleets would be two hundred round trips and a console that takes
    ten seconds to paint.

    Nothing here is decorative. A fleet reads "idle" because it genuinely has
    had no work, not because a seed value said so.
    """
    counters = {c.id: (c.to_dict() or {})
                for c in ledger.db().collection("ledger").limit(limit + 50).stream()}
    out = []
    for p in ledger.db().collection("patients").limit(limit).stream():
        d = p.to_dict() or {}
        c = counters.get(p.id, {})
        waiting = max(0, int(c.get("openExceptions", 0)))
        acted = int(c.get("autonomous", 0)) + int(c.get("systemsTouched", 0))
        out.append({
            "id": p.id,
            "name": (d.get("profile") or {}).get("name", p.id),
            "condition": (d.get("profile") or {}).get("condition"),
            "cohort": bool(d.get("cohort")),
            "waiting": waiting,
            "autonomous": int(c.get("autonomous", 0)),
            # needs_human > active > idle. The grid sorts on this, and a
            # clinician's eye should land on the queue, not the busiest fleet.
            "state": "needs_human" if waiting else ("active" if acted else "idle"),
        })
    out.sort(key=lambda f: (-f["waiting"], -f["autonomous"], f["id"]))
    return {
        "fleets": out,
        "count": len(out),
        "needingHuman": sum(1 for f in out if f["state"] == "needs_human"),
        "active": sum(1 for f in out if f["state"] == "active"),
    }


@app.post("/demo/cohort")
def demo_cohort(count: int = 200):
    """Seed a synthetic cohort. Real FHIR patients, real fleets, idempotent."""
    if not 1 <= count <= 500:
        raise HTTPException(400, "count must be between 1 and 500")
    return cohort.seed(count)


@app.post("/demo/storm")
def demo_storm(count: int = 50, specialty: str = "cardiology"):
    """Hand real work to ``count`` cohort fleets at once.

    Deliberately the Scheduler: it makes no model call, so a burst costs FHIR
    writes rather than tokens, and it genuinely exercises Pub/Sub fan-out, Cloud
    Run concurrency and the lease machinery. That is what the scale screen is
    claiming, so that is what gets exercised.

    Cloud Run max-instances is 4 here, so a large storm queues rather than
    scaling out — visible in the console as tasks draining steadily. That is the
    honest behaviour of the deployment, not a limitation being hidden.
    """
    if not 1 <= count <= 250:
        raise HTTPException(400, "count must be between 1 and 250")
    pts = [p for p in ledger.db().collection("patients").limit(500).stream()
           if (p.to_dict() or {}).get("cohort")][:count]
    if not pts:
        raise HTTPException(409, "no cohort fleets — POST /demo/cohort first")

    def _one(p) -> bool:
        plan = ((p.to_dict() or {}).get("carePlan") or {}).get("instructions") or []
        target = next((i for i in plan if i.get("specialty") == specialty), None) or \
                 next((i for i in plan if i.get("type") == "followup"), None)
        if not target:
            return False
        dispatch.dispatch(p.id, "scheduler", target["id"],
                          {"specialty": target["specialty"], "daysOut": target.get("daysOut", 7)})
        return True

    # Concurrent because each dispatch is a Firestore write plus a Pub/Sub
    # publish we block on for the message id. Serially that is ~0.4s each, so
    # two hundred took 82 seconds — an endpoint nobody can call on camera.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=24) as pool:
        dispatched = sum(1 for ok in pool.map(_one, pts) if ok)
    return {"dispatched": dispatched, "fleets": len(pts), "agent": "scheduler"}


def run() -> None:
    uvicorn.run("app.gateway.main:app", host="0.0.0.0", port=settings.port,
                log_level=settings.log_level.lower())


if __name__ == "__main__":
    run()
