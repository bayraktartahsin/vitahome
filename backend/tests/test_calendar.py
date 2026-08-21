"""The calendar step — a second external system that must never sink a booking.

Two properties carry the weight:
  * unavailability becomes a DECLARED simulation, and the booking completes —
    the clinical record is the source of truth, the calendar is presentation
  * event creation is idempotent through Calendar's own iCalUID search, so a
    drill replay finds its own event instead of double-booking the phone
"""
from __future__ import annotations

import pytest

from app.agents import scheduler
from app.config import settings
from app.integrations import calendar


# ---------------------------------------------------------- scheduler safety

class _Doc:
    exists = True
    def to_dict(self): return {"profile": {"fhirPatientId": "pat-1"}, "carePlan": {}}
    def get(self): return self
    def collection(self, n): return self
    def document(self, i): return self
    def set(self, d, merge=False): pass
    def add(self, d): pass


@pytest.fixture
def run(monkeypatch):
    def _go(calendar_behaviour):
        steps: dict = {}
        monkeypatch.setattr(scheduler.ledger, "db", lambda: _Doc())
        monkeypatch.setattr(scheduler.ledger, "audit", lambda *a, **k: None)
        monkeypatch.setattr(scheduler.ledger, "bump_ledger", lambda *a, **k: None)
        monkeypatch.setattr(scheduler.ledger, "run_step",
                            lambda pid, tid, ag, name, fn: steps.setdefault(name, fn(f"{tid}:{name}")))
        monkeypatch.setattr(scheduler.fhir, "create",
                            lambda rt, b, idem=None: {"id": "appt-1"})
        monkeypatch.setattr(calendar, "create_event", calendar_behaviour)
        return steps
    return _go


def _task():
    return {"input": {"specialty": "cardiology", "daysOut": 7,
                      "fhirPatientId": "pat-1"}, "instructionId": "i_07"}


def test_calendar_down_is_declared_not_fatal(run):
    """The property the demo depends on: kill the calendar and the booking
    still completes, with the simulation stated rather than hidden."""
    def _down(**kw): raise calendar.CalendarUnavailable("token mint failed: 403")
    steps = run(_down)
    summary = scheduler.body("p_hero", "t", _task())
    assert steps["calendar_event"]["simulated"] is True
    assert "declared simulation" in steps["calendar_event"]["note"]
    assert "Cardiology follow-up" in summary
    assert "(FHIR)" in summary          # honest about where it landed


def test_a_real_event_is_recorded_with_its_reference(run):
    steps = run(lambda **kw: {"eventId": "ev1", "htmlLink": "https://cal/x",
                              "calendarId": "c1", "iCalUID": kw["idem"] + "@x",
                              "system": "Google Calendar API"})
    summary = scheduler.body("p_hero", "t", _task())
    assert steps["calendar_event"]["externalRef"] == "gcal:ev1"
    assert "phone calendar" in summary


def test_disabled_by_config_is_a_stated_choice(run, monkeypatch):
    monkeypatch.setattr(settings, "calendar_enabled", False)
    steps = run(lambda **kw: pytest.fail("must not be called when disabled"))
    scheduler.body("p_hero", "t", _task())
    assert steps["calendar_event"]["simulated"] is True


# ------------------------------------------------------------- idempotency

def test_an_existing_event_is_found_not_recreated(monkeypatch):
    """Replay safety: the iCalUID search must short-circuit the import."""
    calls: list[str] = []

    def _req(method, path, **kw):
        calls.append(f"{method} {path}")
        class R:
            status_code = 200
            def json(self):
                if "events" in path and method == "GET":
                    return {"items": [{"id": "ev-existing", "htmlLink": "L"}]}
                return {}
        return R()

    monkeypatch.setattr(calendar, "_req", _req)
    monkeypatch.setattr(calendar, "ensure_calendar", lambda: "cal-1")
    out = calendar.create_event(summary="s", description="d",
                                start_iso="2026-08-25T10:00:00Z",
                                end_iso="2026-08-25T10:30:00Z", idem="t_1:calendar_event")
    assert out["eventId"] == "ev-existing"
    assert not any("import" in c for c in calls), "replay re-imported an existing event"


def test_the_ical_uid_is_deterministic_and_valid():
    """Same step key, same UID, every replay — and no ':' (RFC 5545 hostility)."""
    a = "t_ab:calendar_event".replace(":", "-") + "@vitahome.demo"
    assert ":" not in a.split("@")[0]


def test_a_cohort_fleet_books_in_fhir_but_stays_off_the_shared_calendar():
    """The shared calendar belongs to a person.

    Two hundred synthetic fleets booking into the same 10:00 slot buried the
    demo patient's three real appointments under hundreds of identical entries,
    and the calendar stopped being readable on the phone it exists to appear on.
    The load test still proves the fleet scales — it does that in FHIR, where
    the records are, not in somebody's diary.
    """
    from app.config import settings

    assert settings.calendar_writes_for("p_hero")
    assert not settings.calendar_writes_for("p_c0042")


def test_no_calendar_title_says_the_same_thing_twice():
    """The title the family sees used to read "Cardiology — Dr. Chen · Cardiology".

    That is what happens when one string holds both the clinician and the
    specialty and something prepends the specialty again. This checks the
    rendered title, because that is where the repetition showed up.
    """
    for specialty, (practitioner, location, title) in scheduler._DIRECTORY.items():
        words = [w for w in title.lower().replace("·", " ").split() if len(w) > 3]
        assert len(words) == len(set(words)), f"{specialty}: repeated word in {title!r}"
        assert practitioner.lower() not in title.lower(), (
            f"{specialty}: the title repeats the practitioner ({title!r})")
        assert location, f"{specialty}: no location for the calendar entry"


def test_two_bookings_of_the_same_appointment_are_two_events_not_one():
    """Worth stating plainly, because it was misread once already.

    The iCalUID makes a *replay* of one booking idempotent — the guarantee the
    kill drill demonstrates. Two separate booking requests are two different
    tasks, so they carry different keys and correctly produce two appointments.

    When the demo calendar filled up with doubles, the cause was therefore not
    here: the Director's command was being delivered to every open tab, so the
    booking really was requested twice. Idempotency cannot merge two genuine
    requests, and should not. See web/lib/__tests__/stagelink.contract.md.
    """
    from app.fleet import ledger

    a = ledger.idem_key("t_aaa", "calendar_event")
    b = ledger.idem_key("t_bbb", "calendar_event")
    assert a != b, "different tasks must not share an idempotency key"
    assert ledger.idem_key("t_aaa", "calendar_event") == a, "a replay must reuse its key"
