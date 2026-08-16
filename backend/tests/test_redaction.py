"""PHI must not reach a log line — and the filter that catches it when it does.

The primary control is structural: agents log references, not clinical content.
This tests the second layer, the deterministic scrub, because a defence-in-depth
layer nobody tests is decoration.

Two properties matter more than coverage of any single pattern:
  * a redacted record must not be reconstructible from record.args
  * opaque identifiers must survive untouched, or the logs become useless and
    people switch the filter off
"""
from __future__ import annotations

import logging

import pytest

from app.compliance import redact


# ------------------------------------------------------------- what it scrubs

@pytest.mark.parametrize("raw,gone", [
    ("patient SSN 123-45-6789 on file", "123-45-6789"),
    ("Admitted MRN 88213 yesterday", "88213"),
    ("contact sarah.hayes@example.com about it", "sarah.hayes@example.com"),
    ("call (415) 555-0142 to confirm", "555-0142"),
    ("born 1966-04-02", "1966-04-02"),
    ("Patient: Robert Hayes discharged", "Robert Hayes"),
])
def test_identifiers_are_removed(raw, gone):
    clean, hits = redact.redact(raw)
    assert gone not in clean, f"{gone!r} survived redaction: {clean!r}"
    assert hits


def test_the_category_is_reported_not_just_the_scrub():
    """An operator needs to know WHAT leaked, not only that something did."""
    _, hits = redact.redact("MRN 88213 and bob@example.com")
    assert "mrn" in hits and "email" in hits


# --------------------------------------------------------- what it must keep

@pytest.mark.parametrize("keep", [
    "agent=scheduler pid=p_hero task=t_ab12 attempt=2",
    "step 'fhir_appointment' completed",
    "Appointment/55e38722-78d1-4574-aa33-893d4d0bbf77",
    "gemini model=gemini-3.5-flash-lite ms=3115",
    "leased by nj4·f7210a",
])
def test_opaque_references_survive(keep):
    """Patient ids, task ids and FHIR UUIDs are pseudonymous references — that
    is the whole design. A filter that eats them makes logs useless, and useless
    logs get the filter switched off."""
    clean, hits = redact.redact(keep)
    assert clean == keep and hits == []


def test_a_drug_name_alone_is_not_phi():
    """A schedule template has no patient attached."""
    clean, hits = redact.redact("Ticagrelor 90 mg at 08:00, 20:00")
    assert clean.startswith("Ticagrelor") and hits == []


# ------------------------------------------------------------- the filter

class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(self.format(record))


@pytest.fixture
def logger():
    lg = logging.getLogger("vitahome.test.redaction")
    lg.handlers.clear()
    lg.propagate = False
    lg.setLevel(logging.INFO)
    h = _Capture()
    h.setFormatter(logging.Formatter("%(message)s"))
    h.addFilter(redact.PhiRedactingFilter({}))
    lg.addHandler(h)
    return lg, h


def test_the_filter_scrubs_a_record_on_the_way_out(logger):
    lg, h = logger
    lg.info("seeded Patient: Robert Hayes MRN 88213")
    assert "Robert Hayes" not in h.records[0]
    assert "88213" not in h.records[0]


def test_interpolated_arguments_are_scrubbed_too(logger):
    """The classic hole: redacting record.msg but leaving the PHI sitting in
    record.args for the formatter to put straight back."""
    lg, h = logger
    lg.info("patient %s admitted with MRN %s", "Robert Hayes", "88213")
    out = h.records[0]
    assert "Robert Hayes" not in out and "88213" not in out


def test_a_clean_record_is_left_exactly_alone(logger):
    lg, h = logger
    lg.info("agent=%s task=%s attempt=%s", "scheduler", "t_ab12", 2)
    assert h.records[0] == "agent=scheduler task=t_ab12 attempt=2"


def test_the_filter_counts_what_it_caught():
    counter: dict[str, int] = {}
    f = redact.PhiRedactingFilter(counter)
    for msg in ["MRN 11111", "MRN 22222", "a@b.co"]:
        rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, (), None)
        f.filter(rec)
    assert counter["mrn"] == 2 and counter["email"] == 1


def test_the_filter_never_raises_on_a_malformed_record():
    """Logging is the thing you rely on when everything else is broken. A filter
    that throws while formatting takes the diagnostics down with it."""
    f = redact.PhiRedactingFilter({})
    bad = logging.LogRecord("t", logging.INFO, __file__, 1, "%s %s", ("only-one",), None)
    assert f.filter(bad) is True


# --------------------------------------------------------------- the auditor

def test_scan_returns_clean_for_an_empty_input():
    assert redact.scan([])["clean"] is True


def test_scan_reports_findings_from_the_model(monkeypatch):
    from app.integrations import gemini
    monkeypatch.setattr(
        gemini, "generate_json",
        lambda *a, **k: ({"clean": False, "findings": [
            {"line": "Patient: Robert Hayes", "category": "name",
             "why": "a patient's full name", "severity": "high"}]},
            {"model": "gemma-4-31b-it", "latencyMs": 700}),
    )
    out = redact.scan(["Patient: Robert Hayes"])
    assert out["clean"] is False
    assert out["findings"][0]["category"] == "name"


def test_scan_cannot_report_clean_while_holding_findings(monkeypatch):
    """A model saying clean=true alongside a list of findings contradicts itself.
    The code decides, not the model — same rule as everywhere else here."""
    from app.integrations import gemini
    monkeypatch.setattr(
        gemini, "generate_json",
        lambda *a, **k: ({"clean": True, "findings": [
            {"line": "x", "category": "name", "why": "y", "severity": "high"}]},
            {"model": "gemma-4-31b-it", "latencyMs": 700}),
    )
    assert redact.scan(["x"])["clean"] is False


# ------------------------------------------------ models without schema support

def test_json_is_recovered_from_a_fenced_reply():
    """Gemma has no response_schema, so its answer routinely arrives wrapped in
    a markdown fence or trailed by an explanation nobody asked for."""
    from app.integrations.gemini import _first_json_object
    out = _first_json_object('```json\n{"clean": true, "findings": []}\n```\nHope that helps!')
    assert out == {"clean": True, "findings": []}


def test_a_brace_inside_a_string_does_not_end_the_object():
    """The reason this is brace-matching with string tracking rather than a
    regex — a } in a value would otherwise truncate the parse."""
    from app.integrations.gemini import _first_json_object
    out = _first_json_object('prose {"why": "saw a } here", "n": 1} trailing')
    assert out == {"why": "saw a } here", "n": 1}


def test_an_escaped_quote_does_not_end_the_string():
    from app.integrations.gemini import _first_json_object
    assert _first_json_object(r'{"a": "say \"hi\" {", "b": 2}') == {"a": 'say "hi" {', "b": 2}


def test_no_json_at_all_returns_none():
    from app.integrations.gemini import _first_json_object
    assert _first_json_object("I could not comply with that request.") is None


def test_an_unterminated_object_returns_none():
    from app.integrations.gemini import _first_json_object
    assert _first_json_object('{"clean": true, "findings": [') is None
