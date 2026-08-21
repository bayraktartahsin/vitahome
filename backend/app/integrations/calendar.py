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
from concurrent.futures import ThreadPoolExecutor
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
    # 409 = already imported (the idempotent path). 410 = already deleted, and
    # 404 = never existed — both mean the caller's intent already holds, so a
    # cleanup that races itself is not an error.
    if r.status_code >= 400 and r.status_code not in (409, 410, 404):
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

# Stamped on every event the fleet writes, so its own entries can always be
# told apart from anything else on the calendar — and cleaned up without
# guessing from the title.
_TAG_KEY = "vitahome"


def create_event(*, summary: str, description: str, start_iso: str, end_iso: str,
                 idem: str, location: str = "", patient_id: str = "") -> dict[str, Any]:
    """Create an event exactly once across replays.

    The iCalUID is derived from the ledger's idempotency key, and lookup is
    Calendar's own ``iCalUID`` search — the calendar itself becomes part of the
    effectively-once machinery, the same way the FHIR store does.

    Note what that key does and does not promise. It makes a *replay* of one
    booking idempotent, which is the guarantee the drill demonstrates. Two
    separate booking requests are two appointments, correctly — so a calendar
    that has been demoed against for a week accumulates real entries, and
    ``delete_events`` is how they get cleared.
    """
    cal = ensure_calendar()
    uid = f"{idem.replace(':', '-')}@vitahome.demo"

    existing = _req("GET", f"/calendars/{cal}/events",
                    params={"iCalUID": uid, "maxResults": 1})
    items = existing.json().get("items", [])
    if items:
        ev = items[0]
    else:
        body: dict[str, Any] = {
            "iCalUID": uid,
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": "UTC"},
            "end": {"dateTime": end_iso, "timeZone": "UTC"},
            "status": "confirmed",
            "reminders": {"useDefault": False, "overrides": [
                {"method": "popup", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ]},
            "extendedProperties": {"private": {
                _TAG_KEY: "1", "patientId": patient_id or "unknown"}},
        }
        if location:
            body["location"] = location
        r = _req("POST", f"/calendars/{cal}/events/import", json=body)
        ev = r.json()
        log.info("calendar event created %s", ev.get("id"))

    return {
        "eventId": ev.get("id"),
        "htmlLink": ev.get("htmlLink"),
        "calendarId": cal,
        "iCalUID": uid,
        "system": "Google Calendar API",
    }


def delete_events(patient_id: str = "", include_untagged: bool = False) -> dict[str, Any]:
    """Remove the fleet's own events from the shared calendar.

    Only events this fleet wrote are touched — they carry a private extended
    property, so nothing else on the calendar is at risk even if the calendar
    were shared with other content. Pass a patient id to clear one patient's
    bookings, or nothing to clear all of them.

    Repeated demos leave real appointments behind, which is correct behaviour
    and also makes the calendar unreadable after a few days. This is the
    counterpart every side effect that writes to a human's phone should have.
    """
    cal = ensure_calendar()
    params: dict[str, Any] = {"maxResults": 2500, "singleEvents": "true"}
    if include_untagged:
        # Events written before the fleet started tagging its own entries carry
        # no property to filter on. This calendar is created and owned by the
        # fleet and holds nothing else, so clearing it wholesale is the only way
        # to reach them — and is why the flag has to be asked for by name.
        pass
    elif patient_id:
        params["privateExtendedProperty"] = [f"{_TAG_KEY}=1", f"patientId={patient_id}"]
    else:
        params["privateExtendedProperty"] = f"{_TAG_KEY}=1"

    ids: list[str] = []
    page = None
    while True:
        if page:
            params["pageToken"] = page
        r = _req("GET", f"/calendars/{cal}/events", params=params)
        payload = r.json()
        ids += [ev["id"] for ev in payload.get("items", []) if ev.get("id")]
        page = payload.get("nextPageToken")
        if not page:
            break

    # One request per event, so sixty events is sixty round trips — about six
    # seconds serially, in front of a button somebody presses while a camera is
    # warming up. They are independent deletes, so they go concurrently.
    def _kill(event_id: str) -> bool:
        try:
            _req("DELETE", f"/calendars/{cal}/events/{event_id}")
            return True
        except CalendarUnavailable:
            return False

    deleted = failed = 0
    if ids:
        with ThreadPoolExecutor(max_workers=min(8, len(ids))) as pool:
            for ok in pool.map(_kill, ids):
                if ok:
                    deleted += 1
                else:
                    failed += 1

    log.info("calendar cleanup: %s deleted, %s failed", deleted, failed)
    scope = ("every event on the fleet calendar" if include_untagged
             else patient_id or "all tagged fleet events")
    return {"deleted": deleted, "failed": failed, "calendarId": cal, "scope": scope}


def list_calendars() -> dict[str, Any]:
    """Diagnostic view of every calendar this account holds."""
    payload = _req("GET", "/users/me/calendarList",
                   params={"maxResults": 250}).json()
    items = []
    for c in payload.get("items", []):
        items.append({"id": c.get("id"), "summary": c.get("summary"),
                      "accessRole": c.get("accessRole"),
                      "primary": bool(c.get("primary"))})
    mine = [c for c in items if c["summary"] == settings.calendar_summary]
    return {"total": len(items), "calendars": items,
            "matchingFleetName": len(mine),
            "duplicateCalendars": len(mine) > 1}


def list_events() -> list[dict[str, Any]]:
    """Every event the fleet has on the calendar, with its idempotency key.

    The iCalUID is what makes a replay find its own event instead of writing a
    second one, so when something looks duplicated this is the field that
    settles it: two entries sharing a UID is a bug here, two entries with
    different UIDs are two genuine bookings.
    """
    cal = ensure_calendar()
    out: list[dict[str, Any]] = []
    page = None
    while True:
        params: dict[str, Any] = {"maxResults": 2500, "singleEvents": "true",
                                  "orderBy": "startTime"}
        if page:
            params["pageToken"] = page
        payload = _req("GET", f"/calendars/{cal}/events", params=params).json()
        for ev in payload.get("items", []):
            out.append({
                "summary": ev.get("summary"),
                "start": (ev.get("start") or {}).get("dateTime"),
                "iCalUID": ev.get("iCalUID"),
                "id": ev.get("id"),
                "patientId": ((ev.get("extendedProperties") or {})
                              .get("private") or {}).get("patientId"),
            })
        page = payload.get("nextPageToken")
        if not page:
            return out


def count_events() -> int:
    """How many events the fleet currently has on the shared calendar.

    Worth surfacing rather than inferring: a calendar quietly accumulating
    entries across rehearsals is invisible until it is on camera, and by then
    the demo patient's three appointments are lost among dozens.
    """
    cal = ensure_calendar()
    total, page = 0, None
    while True:
        params: dict[str, Any] = {"maxResults": 2500, "singleEvents": "true",
                                  "fields": "items/id,nextPageToken"}
        if page:
            params["pageToken"] = page
        payload = _req("GET", f"/calendars/{cal}/events", params=params).json()
        total += len(payload.get("items", []))
        page = payload.get("nextPageToken")
        if not page:
            return total


def ping() -> dict[str, Any]:
    """Liveness for /health/deep and the drill preflight."""
    try:
        cal = ensure_calendar()
        return {"ok": True, "calendarId": cal, "link": calendar_link(cal),
                "sharedWith": settings.calendar_share_with or None}
    except CalendarUnavailable as e:
        return {"ok": False, "error": str(e)[:160]}
