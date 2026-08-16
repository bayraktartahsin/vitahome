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
    drill_slow_seconds: int = 0      # >0 opens a kill window between steps (demo only)
    parser_confidence_floor: float = 0.85   # below this → human exception queue, never guessed

    # --- Runtime ---
    port: int = 8080
    log_level: str = "INFO"
    workers_base_url: str = ""       # set on deploy; used for Pub/Sub push endpoints


settings = Settings()
