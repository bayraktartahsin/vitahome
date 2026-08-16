"""Parser — the two rules that make it safe to point at a document.

Both are deterministic Python, deliberately not model behaviour: ordering and
hold-for-human decisions must be inspectable and identical on every run. The
model extracts; this code decides what happens to what it extracted.
"""
from __future__ import annotations

import pytest

from app.agents import parser
from app.config import settings


class _Db:
    """Just enough Firestore for parse() to write its plan."""

    def __init__(self):
        self.written: dict = {}
        self.audit: list = []

    def collection(self, name):
        return self

    def document(self, doc_id):
        return self

    def set(self, data, merge=False):
        self.written.update(data)

    def add(self, data):
        self.audit.append(data)


@pytest.fixture
def parsed(monkeypatch):
    """Drive parse() with a canned model response, so the assertions are about
    our logic rather than about what a model happened to say today."""

    def _run(instructions: list[dict], doc_type: str = "discharge summary"):
        db = _Db()
        monkeypatch.setattr(parser.ledger, "db", lambda: db)
        monkeypatch.setattr(parser.ledger, "audit", lambda *a, **k: None)
        monkeypatch.setattr(parser.ledger, "bump_ledger", lambda *a, **k: None)
        monkeypatch.setattr(
            parser.gemini, "generate_json",
            lambda *a, **k: ({"documentType": doc_type, "instructions": instructions},
                             {"model": "gemini-3.5-flash-lite", "latencyMs": 1031}),
        )
        return parser.parse("p_hero", text="…")

    return _run


def _ins(**kw):
    base = {"lineNo": 1, "text": "x", "type": "other", "criticality": "none",
            "confidence": 0.99}
    return {**base, **kw}


# ------------------------------------------------------------------ ranking

def test_critical_instructions_come_first_regardless_of_page_order(parsed):
    """The whole point: a discharge summary buries the fatal line in the middle
    of the page, in the same font as the parking instructions."""
    out = parsed([
        _ins(lineNo=1, text="No lifting over 10 lbs", criticality="none"),
        _ins(lineNo=2, text="Primary care in 14 days", criticality="caution"),
        _ins(lineNo=7, text="DO NOT STOP ticagrelor", criticality="CRITICAL"),
    ])
    order = [i["criticality"] for i in out["instructions"]]
    assert order == ["CRITICAL", "caution", "none"]
    assert out["instructions"][0]["text"] == "DO NOT STOP ticagrelor"


def test_ties_break_on_confidence_so_the_surest_critical_leads(parsed):
    out = parsed([
        _ins(lineNo=3, text="less sure", criticality="CRITICAL", confidence=0.91),
        _ins(lineNo=9, text="more sure", criticality="CRITICAL", confidence=0.99),
    ])
    assert [i["text"] for i in out["instructions"]] == ["more sure", "less sure"]


def test_ids_are_assigned_after_ranking(parsed):
    """i_01 must be the most consequential instruction, not the topmost line —
    downstream agents and the UI both address instructions by id."""
    out = parsed([
        _ins(lineNo=1, criticality="none", text="minor"),
        _ins(lineNo=2, criticality="CRITICAL", text="fatal"),
    ])
    first = out["instructions"][0]
    assert first["id"] == "i_01" and first["text"] == "fatal"


# --------------------------------------------------------- holding for humans

def test_ambiguous_instructions_are_held_and_never_dispatched(parsed):
    """The dangerous failure mode is a parser that resolves ambiguity by picking
    the likelier reading. It must hand both readings to a person instead."""
    out = parsed([
        _ins(text="Stop the blood pressure medication", ambiguous=True,
             readings=["stop amlodipine", "stop metoprolol"]),
    ])
    held = out["instructions"][0]
    assert held["status"] == "needs_human"
    assert held["heldReason"] == "instruction reads more than one way"
    assert len(held["readings"]) == 2
    assert out["counts"]["heldForHuman"] == 1


def test_low_confidence_is_held_rather_than_guessed(parsed, monkeypatch):
    monkeypatch.setattr(settings, "parser_confidence_floor", 0.85)
    out = parsed([_ins(text="smudged handwriting", confidence=0.42)])
    assert out["instructions"][0]["status"] == "needs_human"
    assert out["instructions"][0]["heldReason"] == "confidence below floor"


def test_confident_unambiguous_instructions_are_ready_to_execute(parsed):
    out = parsed([_ins(text="Cardiology in 7 days", type="followup",
                       criticality="caution", confidence=0.97)])
    ins = out["instructions"][0]
    assert ins["status"] == "pending" and ins["heldReason"] is None
    assert out["counts"]["heldForHuman"] == 0


# ------------------------------------------------------------------ contract

def test_counts_and_provenance_are_reported(parsed):
    """The console shows which model ran and how long it took. If that ever
    stops being reported, the honesty story quietly disappears from the UI."""
    out = parsed([_ins(criticality="CRITICAL"), _ins()])
    assert out["counts"] == {"total": 2, "critical": 1, "heldForHuman": 0}
    assert out["model"] == "gemini-3.5-flash-lite"
    assert out["latencyMs"] == 1031


def test_empty_input_is_rejected_before_a_model_call(parsed):
    with pytest.raises(parser.gemini.ModelError):
        parser.parse("p_hero", text="   ")


def test_a_non_medical_document_yields_no_instructions(parsed):
    """Handing the fleet a restaurant menu must produce nothing, not invented
    medical content. Judges are invited to try exactly this."""
    out = parsed([], doc_type="restaurant menu")
    assert out["instructions"] == []
    assert out["documentType"] == "restaurant menu"
