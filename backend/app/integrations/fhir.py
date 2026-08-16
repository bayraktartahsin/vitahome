"""Google Cloud Healthcare API — FHIR R4 client.

This is the clinical source of truth. Not a mock: a real managed FHIR store.
Every write carries the ledger's idempotency key as a FHIR ``identifier`` and
we search-before-create, so a crash between "wrote to FHIR" and "recorded the
step" still cannot produce a duplicate.
"""
from __future__ import annotations

from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

from ..config import settings

IDEM_SYSTEM = "https://vitahome.dev/idempotency-key"

_creds = None


def _token() -> str:
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
    }


def search(resource_type: str, params: dict[str, str]) -> list[dict[str, Any]]:
    r = httpx.get(f"{settings.fhir_base}/{resource_type}",
                  headers=_headers(), params=params, timeout=20.0)
    r.raise_for_status()
    bundle = r.json()
    return [e["resource"] for e in bundle.get("entry", [])]


def find_by_idem(resource_type: str, key: str) -> dict[str, Any] | None:
    hits = search(resource_type, {"identifier": f"{IDEM_SYSTEM}|{key}"})
    return hits[0] if hits else None


def create(resource_type: str, body: dict[str, Any], idem: str | None = None) -> dict[str, Any]:
    """Create a resource, idempotently when ``idem`` is supplied."""
    if idem:
        existing = find_by_idem(resource_type, idem)
        if existing:
            return existing            # a previous attempt already wrote this
        body = {**body, "identifier": [*body.get("identifier", []),
                                       {"system": IDEM_SYSTEM, "value": idem}]}
    r = httpx.post(f"{settings.fhir_base}/{resource_type}",
                   headers=_headers(), json={**body, "resourceType": resource_type},
                   timeout=30.0)
    r.raise_for_status()
    return r.json()


def read(resource_type: str, rid: str) -> dict[str, Any]:
    r = httpx.get(f"{settings.fhir_base}/{resource_type}/{rid}",
                  headers=_headers(), timeout=20.0)
    r.raise_for_status()
    return r.json()


def ping() -> dict[str, Any]:
    """Cheap liveness probe used by /health — proves the FHIR store is reachable."""
    try:
        r = httpx.get(f"{settings.fhir_base}/Patient", headers=_headers(),
                      params={"_count": "1"}, timeout=10.0)
        return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}
