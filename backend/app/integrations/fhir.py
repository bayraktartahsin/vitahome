"""Google Cloud Healthcare API — FHIR R4 client.

This is the clinical source of truth. Not a mock: a real managed FHIR store.
Every write carries the ledger's idempotency key as a FHIR ``identifier`` and
we search-before-create, so a crash between "wrote to FHIR" and "recorded the
step" still cannot produce a duplicate.
"""
from __future__ import annotations

import threading
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

from ..config import settings

IDEM_SYSTEM = "https://vitahome.dev/idempotency-key"

_creds = None
_creds_lock = threading.Lock()


def _token() -> str:
    """Return a valid access token, safely under concurrency.

    The lock is not paranoia. Without it, several threads that all observe an
    expired credential call ``refresh()`` at the same time, and one of them
    reads ``_creds.token`` while another is midway through swapping it — which
    surfaces as a 401 from a request that had every right to succeed.

    That is exactly what happened seeding two hundred cohort patients across
    sixteen threads: 189 succeeded and 11 came back 401. It is not specific to
    seeding — agents run concurrently on Cloud Run, so this was a live defect
    that happened to need volume to show itself.

    Holding the lock across the refresh also collapses sixteen simultaneous
    refreshes into one. It is contended only while a token is actually being
    renewed, which is roughly hourly.
    """
    global _creds
    with _creds_lock:
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
    _raise_for_outcome(r, resource_type)
    bundle = r.json()
    return [e["resource"] for e in bundle.get("entry", [])]


def find_by_idem(resource_type: str, key: str) -> dict[str, Any] | None:
    hits = search(resource_type, {"identifier": f"{IDEM_SYSTEM}|{key}"})
    return hits[0] if hits else None


class FhirError(RuntimeError):
    """Carries the OperationOutcome diagnostics — FHIR 400s are precise, and
    swallowing them turns a five-minute fix into an hour of guessing."""

    def __init__(self, status: int, diagnostics: str, resource_type: str):
        super().__init__(f"FHIR {resource_type} {status}: {diagnostics}")
        self.status = status
        self.diagnostics = diagnostics


def _raise_for_outcome(r: httpx.Response, resource_type: str) -> None:
    if r.is_success:
        return
    diagnostics = r.text[:400]
    try:
        for issue in r.json().get("issue", []):
            d = issue.get("diagnostics") or (issue.get("details") or {}).get("text")
            if d:
                diagnostics = d
                break
    except Exception:  # noqa: BLE001
        pass
    raise FhirError(r.status_code, diagnostics, resource_type)


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
    _raise_for_outcome(r, resource_type)
    return r.json()


def update(resource_type: str, rid: str, body: dict[str, Any]) -> dict[str, Any]:
    """Full-resource update (FHIR PUT).

    Naturally idempotent: the caller sends the desired end state, so replaying
    it converges rather than accumulating. This is how a medication gets stopped
    — the resource is rewritten with ``status: stopped``, and doing that twice
    is indistinguishable from doing it once.
    """
    r = httpx.put(f"{settings.fhir_base}/{resource_type}/{rid}",
                  headers=_headers(),
                  json={**body, "resourceType": resource_type, "id": rid},
                  timeout=30.0)
    _raise_for_outcome(r, resource_type)
    return r.json()


def read(resource_type: str, rid: str) -> dict[str, Any]:
    r = httpx.get(f"{settings.fhir_base}/{resource_type}/{rid}",
                  headers=_headers(), timeout=20.0)
    _raise_for_outcome(r, resource_type)
    return r.json()


def ping() -> dict[str, Any]:
    """Cheap liveness probe used by /health — proves the FHIR store is reachable."""
    try:
        r = httpx.get(f"{settings.fhir_base}/Patient", headers=_headers(),
                      params={"_count": "1"}, timeout=10.0)
        return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}
