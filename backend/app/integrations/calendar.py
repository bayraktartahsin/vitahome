"""Google Calendar — the real action surface.

The Scheduler does not stop at the clinical record. After the FHIR Appointment
is written, the same booking lands as an event in a real Google Calendar that
the fleet owns and has shared to the family's account — so the appointment
simply appears on their phone. No mock, no screenshot: the Calendar API, called
with the same idempotency discipline as everything else.

Two design constraints shaped this module:

1. **Service accounts cannot email attendee invites** without Workspace
   domain-wide delegation — a hard API restriction, not a permissions gap. So
   the fleet does the stronger thing instead: it owns a calendar, shares it to
   the configured account once, and writes events into it. Appearing on the
   phone's calendar beats an email that asks to be accepted.

2. **The default Cloud Run token does not carry the Calendar scope** (it is a
   cloud-platform token, and Calendar is not a Cloud API). Rather than gamble
   on metadata-server scope parameters, the service account mints itself a
   calendar-scoped token through the IAM Credentials API — deterministic
   everywhere, and the only IAM it needs is tokenCreator on itself.

Idempotency uses the Calendar-native mechanism: every event is imported with an
``iCalUID`` derived from the ledger's step key, and creation is
search-before-create on that UID. A replayed step finds its own event and
stops — the same trick the FHIR writes use with ``identifier``.

Every failure raises ``CalendarUnavailable``; the Scheduler catches exactly
that and records a *declared* simulation instead. A booking never fails because
a calendar was unreachable — the clinical record is the source of truth, the
calendar is how humans see it.
"""
from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

from ..config import settings

log = logging.getLogger("vitahome.calendar")

_SCOPE = "https://www.googleapis.com/auth/calendar"
_API = "https://www.googleapis.com/calendar/v3"


class CalendarUnavailable(RuntimeError):
    """The calendar could not be reached or written.

    Its own type because the caller's correct response is a declared
    simulation, not a failed booking.
    """


# --------------------------------------------------------------------------
# token — self-minted with the calendar scope, cached until near expiry
# --------------------------------------------------------------------------

_tok_lock = threading.Lock()
_tok: dict[str, Any] = {"value": None, "exp": 0.0}


def _sa_email() -> str:
    return f"{settings.gcp_project_number}-compute@developer.gserviceaccount.com"


def _token() -> str:
    with _tok_lock:
        if _tok["value"] and time.time() < _tok["exp"] - 60:
            return _tok["value"]
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not creds.valid:
            creds.refresh(google.auth.transport.requests.Request())
        r = httpx.post(
            f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{_sa_email()}:generateAccessToken",
            headers={"Authorization": f"Bearer {creds.token}"},
            json={"scope": [_SCOPE], "lifetime": "3600s"},
            timeout=15.0,
        )
        if r.status_code != 200:
            raise CalendarUnavailable(f"token mint failed: {r.status_code} {r.text[:160]}")
        _tok["value"] = r.json()["accessToken"]
        _tok["exp"] = time.time() + 3500
        return _tok["value"]


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}


def _req(method: str, path: str, **kw: Any) -> httpx.Response:
    try:
        r = httpx.request(method, f"{_API}{path}", headers=_headers(),
                          timeout=20.0, **kw)
    except httpx.HTTPError as e:
        raise CalendarUnavailable(f"calendar unreachable: {e}") from e
    if r.status_code >= 400 and r.status_code != 409:
        raise CalendarUnavailable(f"calendar {method} {path}: {r.status_code} {r.text[:160]}")
    return r


# --------------------------------------------------------------------------
# the fleet's calendar
# --------------------------------------------------------------------------

_cal_lock = threading.Lock()
_cal_id: str | None = None


def ensure_calendar() -> str:
    """Find or create the fleet's calendar and share it, once per process.

    Find-before-create on the summary, so every instance and every replay
    converges on one calendar rather than minting a new one per cold start.
    """
    global _cal_id
    with _cal_lock:
        if _cal_id:
            return _cal_id

        listing = _req("GET", "/users/me/calendarList", params={"maxResults": 100})
        for item in listing.json().get("items", []):
            if item.get("summary") == settings.calendar_summary:
                _cal_id = item["id"]
                break
        else:
            created = _req("POST", "/calendars",
                           json={"summary": settings.calendar_summary,
                                 "timeZone": "UTC"})
            _cal_id = created.json()["id"]
            log.info("created fleet calendar %s", _cal_id)

        # Share to the configured human. Idempotent: inserting an existing ACL
        # rule just updates it. This is what makes the events appear on a real
        # phone — the fleet owns the calendar, the family reads it.
        if settings.calendar_share_with:
            _req("POST", f"/calendars/{_cal_id}/acl",
                 json={"role": "writer",
                       "scope": {"type": "user",
                                 "value": settings.calendar_share_with}})
        return _cal_id


def calendar_link(cal_id: str | None = None) -> str:
    """The link a person opens to add this calendar to their own Google
    Calendar — the ``cid`` is just the calendar id, base64url without padding."""
    cid = base64.urlsafe_b64encode((cal_id or ensure_calendar()).encode()) \
        .decode().rstrip("=")
    return f"https://calendar.google.com/calendar/u/0/r?cid={cid}"


# --------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------

def create_event(*, summary: str, description: str, start_iso: str, end_iso: str,
                 idem: str) -> dict[str, Any]:
    """Create an event exactly once across replays.

    The iCalUID is derived from the ledger's idempotency key, and lookup is
    Calendar's own ``iCalUID`` search — the calendar itself becomes part of the
    effectively-once machinery, the same way the FHIR store does.
    """
    cal = ensure_calendar()
    uid = f"{idem.replace(':', '-')}@vitahome.demo"

    existing = _req("GET", f"/calendars/{cal}/events",
                    params={"iCalUID": uid, "maxResults": 1})
    items = existing.json().get("items", [])
    if items:
        ev = items[0]
    else:
        r = _req("POST", f"/calendars/{cal}/events/import", json={
            "iCalUID": uid,
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": "UTC"},
            "end": {"dateTime": end_iso, "timeZone": "UTC"},
            "status": "confirmed",
        })
        ev = r.json()
        log.info("calendar event created %s", ev.get("id"))

    return {
        "eventId": ev.get("id"),
        "htmlLink": ev.get("htmlLink"),
        "calendarId": cal,
        "iCalUID": uid,
        "system": "Google Calendar API",
    }


def ping() -> dict[str, Any]:
    """Liveness for /health/deep and the drill preflight."""
    try:
        cal = ensure_calendar()
        return {"ok": True, "calendarId": cal, "link": calendar_link(cal),
                "sharedWith": settings.calendar_share_with or None}
    except CalendarUnavailable as e:
        return {"ok": False, "error": str(e)[:160]}
