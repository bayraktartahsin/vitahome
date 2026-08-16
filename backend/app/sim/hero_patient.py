"""The hero patient — Robert Hayes, 60M, post-PCI.

A synthetic patient carrying the demo's emotional payload: a real discharge
document whose most dangerous instruction is *"DO NOT STOP ticagrelor without
cardiology"*. Stopping dual antiplatelet therapy early after a drug-eluting
stent can cause stent thrombosis, which is frequently fatal. Every Gemini tier
we measured caught that line — it is the moment the demo opens on.

Entirely synthetic. No real patient data anywhere in this project.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..fleet import ledger
from ..integrations import fhir

HERO_ID = "p_hero"

DISCHARGE_TEXT = """DISCHARGE SUMMARY — Mercy General Hospital
Patient: Robert Hayes, 60M    MRN 88213    Admitted 08/12  Discharged 08/15
Diagnosis: NSTEMI, s/p PCI with drug-eluting stent to LAD.

MEDICATIONS ON DISCHARGE
  1. Aspirin 81 mg PO daily — indefinite
  2. Ticagrelor 90 mg PO twice daily for 12 months
     ** DO NOT STOP without speaking to cardiology **
  3. Atorvastatin 80 mg PO nightly
  4. Metoprolol succinate 25 mg PO daily
  5. STOP amlodipine 5 mg — replaced by metoprolol

FOLLOW-UP
  - Cardiology (Dr. Chen) in 7 days
  - Primary care in 14 days
  - Cardiac rehab intake within 21 days

RESTRICTIONS
  - No lifting over 10 lbs for 1 week
  - No driving for 3 days

RETURN TO EMERGENCY IF
  chest pain · shortness of breath at rest · bleeding · fainting
"""

# Pre-parsed instructions. The Parser agent produces this shape from the image;
# seeding it lets every downstream agent be built and tested independently.
INSTRUCTIONS: list[dict[str, Any]] = [
    {"id": "i_01", "lineNo": 6, "type": "medication", "text": "Aspirin 81 mg PO daily — indefinite",
     "criticality": "caution", "confidence": 0.98, "status": "pending"},
    {"id": "i_02", "lineNo": 7, "type": "medication",
     "text": "Ticagrelor 90 mg PO twice daily for 12 months — DO NOT STOP without speaking to cardiology",
     "criticality": "CRITICAL", "confidence": 0.99, "status": "pending",
     "why": "Stopping dual antiplatelet therapy early after a drug-eluting stent can cause stent thrombosis, which is frequently fatal."},
    {"id": "i_03", "lineNo": 9, "type": "medication", "text": "Atorvastatin 80 mg PO nightly",
     "criticality": "none", "confidence": 0.98, "status": "pending"},
    {"id": "i_04", "lineNo": 10, "type": "medication", "text": "Metoprolol succinate 25 mg PO daily",
     "criticality": "none", "confidence": 0.97, "status": "pending"},
    {"id": "i_05", "lineNo": 11, "type": "medication_stop",
     "text": "STOP amlodipine 5 mg — replaced by metoprolol",
     "criticality": "caution", "confidence": 0.96, "status": "pending"},
    {"id": "i_06", "lineNo": 14, "type": "followup", "text": "Cardiology (Dr. Chen) in 7 days",
     "specialty": "cardiology", "daysOut": 7,
     "criticality": "caution", "confidence": 0.97, "status": "pending"},
    {"id": "i_07", "lineNo": 15, "type": "followup", "text": "Primary care in 14 days",
     "specialty": "primary care", "daysOut": 14,
     "criticality": "none", "confidence": 0.96, "status": "pending"},
    {"id": "i_08", "lineNo": 16, "type": "followup", "text": "Cardiac rehab intake within 21 days",
     "specialty": "cardiac rehab", "daysOut": 21,
     "criticality": "none", "confidence": 0.94, "status": "pending"},
    {"id": "i_09", "lineNo": 19, "type": "restriction", "text": "No lifting over 10 lbs for 1 week",
     "criticality": "none", "confidence": 0.97, "status": "pending"},
    {"id": "i_10", "lineNo": 20, "type": "restriction", "text": "No driving for 3 days",
     "criticality": "none", "confidence": 0.97, "status": "pending"},
    {"id": "i_11", "lineNo": 23, "type": "red_flag",
     "text": "Return to emergency if: chest pain, shortness of breath at rest, bleeding, fainting",
     "criticality": "CRITICAL", "confidence": 0.98, "status": "pending",
     "flags": ["chest pain", "shortness of breath at rest", "bleeding", "fainting"]},
]


def seed() -> dict[str, Any]:
    """Create the hero patient in FHIR + Firestore. Idempotent."""
    # --- FHIR Patient (idempotent on our own identifier) ---
    patient = fhir.create("Patient", {
        "name": [{"family": "Hayes", "given": ["Robert"]}],
        "gender": "male",
        "birthDate": "1966-04-02",
    }, idem="hero-patient-v1")
    fhir_id = patient.get("id")

    # --- the medication the discharge says to STOP (must pre-exist to be reconciled) ---
    fhir.create("MedicationRequest", {
        "status": "active",
        "intent": "order",
        "subject": {"reference": f"Patient/{fhir_id}"},
        "medicationCodeableConcept": {"text": "Amlodipine 5 mg"},
        "dosageInstruction": [{"text": "5 mg PO daily"}],
    }, idem="hero-med-amlodipine-v1")

    fhir.create("MedicationRequest", {
        "status": "active",
        "intent": "order",
        "subject": {"reference": f"Patient/{fhir_id}"},
        "medicationCodeableConcept": {"text": "Aspirin 81 mg"},
        "dosageInstruction": [{"text": "81 mg PO daily"}],
    }, idem="hero-med-aspirin-v1")

    # --- Firestore fleet state ---
    ledger.db().collection("patients").document(HERO_ID).set({
        "profile": {
            "name": "Robert Hayes", "age": 60, "fhirPatientId": fhir_id,
            "caregiver": "Sarah Hayes (daughter)",
            "note": "synthetic patient — no real PHI",
        },
        "fleetState": "active",
        "carePlan": {
            "sourceDocument": DISCHARGE_TEXT,
            "parsedAt": datetime.now(timezone.utc),
            "parserVersion": "seed-v1",
            "instructions": INSTRUCTIONS,
        },
    }, merge=True)

    ledger.audit(HERO_ID, "action", "seed",
                 f"hero patient seeded — FHIR Patient/{fhir_id}, {len(INSTRUCTIONS)} instructions")

    return {"patientId": HERO_ID, "fhirPatientId": fhir_id,
            "instructions": len(INSTRUCTIONS),
            "critical": [i["id"] for i in INSTRUCTIONS if i["criticality"] == "CRITICAL"]}
