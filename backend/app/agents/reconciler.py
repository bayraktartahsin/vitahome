"""💊 Reconciler — what he was taking vs. what the document says, and The Refusal.

Medication reconciliation at discharge is one of the best-documented failure
points in medicine. The mechanism is mundane: the summary lists new drugs, a
boilerplate line says "resume home medications", and nobody notices that the two
statements contradict each other about one specific pill. The patient goes home
and takes both, or neither.

So this agent does the comparison — and then does the thing that matters more:

    **It stops at the contradiction instead of resolving it.**

That is `Refusal`, and it is the product thesis rendered as control flow. The
fleet applies every change it can justify, and where the document genuinely
reads two ways it assembles both readings and hands a licensed human the
decision. It does not pick the likelier one. Picking the likelier one is how you
build something that is right 95% of the time about which blood thinner a
post-stent patient should be taking.

**The model advises; only code decides.** Gemini compares the lists and *flags*
conflicts. Whether a flag becomes an action or a refusal is a deterministic
branch below — inspectable, testable, and identical on every run. A model cannot
talk this agent into applying a change it marked ambiguous.

Steps, each independently idempotent:

  1. fetch_active   read current MedicationRequests from the FHIR store
  2. assess         Gemini compares them against the discharge instructions
  3. apply_changes  write the unambiguous ones (PUT/POST, both replay-safe)
  → then refuse, if anything was flagged
"""
from __future__ import annotations

import logging
from typing import Any

from ..config import settings
from ..fleet import ledger
from ..fleet.runtime import Refusal
from ..integrations import fhir, gemini

log = logging.getLogger("vitahome.reconciler")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "drug": {"type": "string"},
                    "action": {"type": "string", "enum": ["start", "continue", "stop"]},
                    "dose": {"type": "string"},
                    "instructionId": {"type": "string"},
                    "activeRequestId": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["drug", "action", "rationale"],
            },
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "drug": {"type": "string"},
                    "question": {"type": "string"},
                    "readings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "reading": {"type": "string"},
                                "source": {"type": "string"},
                                "consequence": {"type": "string"},
                            },
                            "required": ["reading", "source"],
                        },
                    },
                },
                "required": ["drug", "question", "readings"],
            },
        },
    },
    "required": ["changes", "conflicts"],
}

PROMPT = """You are reconciling a patient's discharge medication instructions against
the medications they are currently recorded as taking.

CURRENTLY ACTIVE (from the clinical record):
{active}

DISCHARGE INSTRUCTIONS (from the document):
{instructions}

Produce two lists.

`changes` — every medication change you are CONFIDENT about:
  action=start    on the discharge list, not currently active
  action=continue on the discharge list and already active
  action=stop     the discharge document explicitly says to stop it
  Include activeRequestId when the drug matches something in the active list.
  Include instructionId when it comes from a specific discharge instruction.
  rationale: one short sentence citing what you matched.

`conflicts` — every medication where the document supports MORE THAN ONE
reading, and the readings imply different actions. This is the important list.
The classic case is a blanket "resume home medications" line sitting alongside a
specific instruction to stop one of those home medications: both statements are
in the document, they contradict each other, and only a clinician can say which
governs.

For each conflict give:
  question:  what a clinician must decide, in one sentence
  readings:  each interpretation, with `source` naming the line or record it
             comes from, and `consequence` stating what the patient would
             actually take under that reading.

Do NOT resolve a conflict by choosing the likelier reading. Do NOT put a drug in
both lists. If you are unsure whether something is a conflict, it is a conflict."""


def _active_medications(fhir_patient: str) -> list[dict[str, Any]]:
    """Read the clinical record inside our own IAM scope.

    The Pub/Sub message carried a reference, not the medication list — PHI is
    fetched by the agent that needs it, never shipped through the queue.
    """
    out = []
    for mr in fhir.search("MedicationRequest",
                          {"subject": f"Patient/{fhir_patient}", "status": "active",
                           "_count": "50"}):
        out.append({
            "id": mr.get("id"),
            "drug": (mr.get("medicationCodeableConcept") or {}).get("text", "?"),
            "dose": ((mr.get("dosageInstruction") or [{}])[0]).get("text", ""),
        })
    return out


def _fmt(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    if not rows:
        return "  (none)"
    return "\n".join(
        "  - " + " · ".join(f"{k}={r[k]}" for k in keys if r.get(k)) for r in rows
    )


def body(pid: str, task_id: str, task: dict[str, Any]) -> str:
    snap = ledger.db().collection("patients").document(pid).get()
    doc = snap.to_dict() or {}
    fhir_patient = (doc.get("profile") or {}).get("fhirPatientId")
    if not fhir_patient:
        raise Refusal("no FHIR patient record is linked to this fleet",
                      options=["Link the patient record", "Seed the demo patient"])

    med_instructions = [
        {"id": i.get("id"), "text": i.get("text"), "type": i.get("type"),
         "drug": i.get("drug"), "dose": i.get("dose")}
        for i in (doc.get("carePlan") or {}).get("instructions", [])
        if i.get("type") in ("medication", "medication_stop", "other")
    ]
    if not med_instructions:
        raise Refusal("no medication instructions on this care plan to reconcile",
                      options=["Re-parse the discharge document"])

    # ---- step 1: what is the record actually saying today ------------------
    def _fetch(_key: str) -> dict[str, Any]:
        active = _active_medications(fhir_patient)
        return {"active": active, "count": len(active),
                "system": "Google Cloud Healthcare API (FHIR R4)"}

    current = ledger.run_step(pid, task_id, "reconciler", "fetch_active", _fetch)
    ledger.bump_ledger(pid, "systemsTouched")

    # ---- step 2: compare (the model advises) -------------------------------
    def _assess(_key: str) -> dict[str, Any]:
        out, meta = gemini.generate_json(
            PROMPT.format(
                active=_fmt(current["active"], ("drug", "dose", "id")),
                instructions=_fmt(med_instructions, ("id", "text")),
            ),
            SCHEMA,
            model=settings.model_reason,   # judgement, not extraction — worth the 1.3s
        )
        return {**out, "model": meta["model"], "latencyMs": meta["latencyMs"]}

    assessment = ledger.run_step(pid, task_id, "reconciler", "assess", _assess)
    changes = assessment.get("changes") or []
    conflicts = assessment.get("conflicts") or []

    # ---- step 3: apply only what is unambiguous (the code decides) ---------
    # Note the ordering: we apply BEFORE refusing. A refusal on one drug must not
    # hold up four changes nobody disputes — that would make the safe behaviour
    # expensive, and expensive safety gets switched off.
    conflicted = {c["drug"].strip().lower() for c in conflicts if c.get("drug")}

    def _apply(key: str) -> dict[str, Any]:
        applied: list[dict[str, Any]] = []
        for ch in changes:
            drug = (ch.get("drug") or "").strip()
            if not drug or drug.lower() in conflicted:
                continue                      # a flagged drug is never auto-applied
            action = ch.get("action")
            if action == "stop" and ch.get("activeRequestId"):
                mr = fhir.read("MedicationRequest", ch["activeRequestId"])
                fhir.update("MedicationRequest", mr["id"], {**mr, "status": "stopped"})
                applied.append({"drug": drug, "action": "stop",
                                "ref": f"MedicationRequest/{mr['id']}"})
            elif action == "start":
                res = fhir.create("MedicationRequest", {
                    "status": "active", "intent": "order",
                    "subject": {"reference": f"Patient/{fhir_patient}"},
                    "medicationCodeableConcept": {"text": drug},
                    "dosageInstruction": [{"text": ch.get("dose") or drug}],
                }, idem=f"{key}:{drug.lower().replace(' ', '-')}")
                applied.append({"drug": drug, "action": "start",
                                "ref": f"MedicationRequest/{res.get('id')}"})
            else:
                applied.append({"drug": drug, "action": "continue"})
        return {"applied": applied, "count": len(applied),
                "skippedAsConflicted": sorted(conflicted)}

    result = ledger.run_step(pid, task_id, "reconciler", "apply_changes", _apply)

    # ---- The Refusal -------------------------------------------------------
    if conflicts:
        c = conflicts[0]                      # one decision at a time; queue the rest
        options = [
            f"{r['reading']}  ({r.get('source', 'source unclear')})"
            for r in c.get("readings", [])
        ] + ["Ask the discharging team to clarify"]
        ledger.db().collection("patients").document(pid).set(
            {"openConflicts": conflicts}, merge=True
        )
        raise Refusal(
            f"{c['drug']} — {c['question']}",
            options=options,
        )

    n = result["count"]
    return f"reconciled {n} medication change{'s' if n != 1 else ''}, no conflicts"
