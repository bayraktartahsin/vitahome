"""Runtime configuration. Everything from env; secrets injected by Cloud Run."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Gemini ---
    gemini_api_key: str = ""
    model_fast: str = "gemini-3.5-flash-lite"   # 1.03s measured — high-volume extraction
    model_reason: str = "gemini-3.7-flash"      # 2.35s measured — reasoning + refusal judgment
    model_tts: str = "gemini-3.1-flash-tts-preview"
    # Gemma for the log audit: it is pattern recognition, not judgement, and
    # the compliance story reads better when the model reading your logs is
    # the smallest one that can do the job rather than the most capable.
    model_redact: str = "gemma-4-31b-it"

    # --- GCP ---
    gcp_project: str = "gen-lang-client-0109591583"
    gcp_project_number: str = "205100594497"
    region: str = "us-central1"

    # --- Healthcare API (FHIR R4) ---
    hc_location: str = "us-central1"
    hc_dataset: str = "vitahome"
    hc_fhir_store: str = "clinical"

    @property
    def fhir_base(self) -> str:
        return (
            f"https://healthcare.googleapis.com/v1/projects/{self.gcp_project}"
            f"/locations/{self.hc_location}/datasets/{self.hc_dataset}"
            f"/fhirStores/{self.hc_fhir_store}/fhir"
        )

    # --- Pub/Sub ---
    topic_fleet_work: str = "fleet-work"
    topic_vitals: str = "vitals-sim"

    # --- Fleet runtime ---
    lease_seconds: int = 60          # task lease; supervisor flags stale beyond this
    heartbeat_seconds: int = 5       # agent heartbeat cadence
    max_attempts: int = 5            # poison-message guard: stop redelivering after this
    drill_slow_seconds: int = 0            # >0 opens a kill window (demo only)
    drill_slow_step: str = "fhir_appointment"  # ...on exactly this step, so the window is predictable
    parser_confidence_floor: float = 0.85   # below this → human exception queue, never guessed

    # How long a human has to answer an escalation before the console shows it
    # as breached. Displayed as a countdown, never auto-resolved — a breached
    # SLA stays breached, because a timer that quietly clears itself is worse
    # than no timer.
    sla_minutes: dict[str, int] = {"emergency": 5, "urgent": 30, "routine": 480}

    # Where each agent physically runs, as JSON: {"scheduler": "https://..."}.
    # Empty means the gateway hosts it. This exists so the registry can PROVE
    # the decoupling claim — an agent's location is configuration, not code.
    agent_services: str = ""

    # --- Google Calendar (the real action surface) ---
    calendar_enabled: bool = True
    calendar_summary: str = "VitaHome — appointments (demo)"
    # Who the fleet's calendar is shared with — the account whose phone the
    # events appear on. Change per deployment, not per booking.
    calendar_share_with: str = "info@gravitilabs.com"
    # Which fleets may write to that shared calendar. It belongs to a person,
    # so the load-test cohort stays off it: 200 synthetic fleets booking into
    # the same 10:00 slot buries the demo patient's real appointments and makes
    # the calendar useless to look at. Cohort fleets still write to FHIR — the
    # scale claim is about the fleet, not about filling somebody's diary.
    # Set to "*" to let every fleet write.
    calendar_patients: str = "p_hero"
    # Whether anyone with the link may read the fleet's calendar. On during
    # judging so a reviewer can subscribe and watch the bookings arrive; the
    # calendar holds nothing but synthetic demo appointments.
    calendar_public: bool = True

    # Optional gate for destructive demo endpoints (reset/cohort/storm/chaos).
    # Empty = open, which is the deliberate posture while judges need to drive
    # the chaos panel themselves; set it and callers must send X-Demo-Key.
    demo_key: str = ""

    @property
    def agent_service_map(self) -> dict[str, str]:
        import json
        try:
            return json.loads(self.agent_services) if self.agent_services else {}
        except json.JSONDecodeError:
            return {}

    # --- Runtime ---
    port: int = 8080
    log_level: str = "INFO"
    workers_base_url: str = ""       # set on deploy; used for Pub/Sub push endpoints

    def calendar_writes_for(self, patient_id: str) -> bool:
        """May this fleet write to the calendar shared with a real person?"""
        allowed = {p.strip() for p in self.calendar_patients.split(",") if p.strip()}
        return "*" in allowed or patient_id in allowed


settings = Settings()
