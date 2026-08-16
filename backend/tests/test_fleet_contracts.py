"""Contract tests — the invariants a refactor must never silently break.

Deliberately free of Firestore/FHIR/Pub/Sub: these run in milliseconds in CI and
are deterministic. Integration behaviour is covered by the live drill.
"""
from __future__ import annotations

import re

import pytest

from app.fleet import registry
from app.fleet.ledger import idem_key
from app.fleet.runtime import Escalation, Refusal


# --------------------------------------------------------------- idempotency

def test_idem_key_is_deterministic_across_replays():
    """The whole recovery story depends on this being stable."""
    assert idem_key("t_abc", "fhir_appointment") == idem_key("t_abc", "fhir_appointment")


def test_idem_key_separates_steps_and_tasks():
    assert idem_key("t_abc", "step1") != idem_key("t_abc", "step2")
    assert idem_key("t_abc", "step1") != idem_key("t_xyz", "step1")


def test_idem_key_is_safe_as_an_external_identifier():
    """It is written into FHIR identifiers and Calendar iCalUIDs."""
    key = idem_key("t_01J8XYZ", "fhir_appointment")
    assert re.fullmatch(r"[A-Za-z0-9_:\-]+", key), key


# ------------------------------------------------------------ control flow

def test_refusal_carries_reason_and_options():
    """A refusal must hand the human a decision, not just a complaint."""
    r = Refusal("two plausible readings", ["resume all", "hold amlodipine"])
    assert r.reason == "two plausible readings"
    assert len(r.options) == 2


def test_refusal_is_not_an_error_path():
    """Refusal and Escalation must not be confused with failures — failures
    get redelivered by Pub/Sub, refusals must not be."""
    assert issubclass(Refusal, Exception)
    assert not issubclass(Refusal, RuntimeError)
    assert not issubclass(Escalation, RuntimeError)


def test_escalation_carries_context_for_the_clinician():
    e = Escalation("chest pain reported", {"vitals": "hr 104", "since": "02:00"})
    assert e.trigger == "chest pain reported"
    assert e.context["vitals"] == "hr 104"


# ---------------------------------------------------------------- registry

def test_registry_exposes_the_whole_fleet():
    reg = registry.registry()
    assert reg["protocol"] == "a2a-agent-card/v1"
    assert len(reg["agents"]) == 7


def test_adk_agent_names_are_valid_identifiers():
    """ADK rejects hyphens in node names — this test exists because we hit it."""
    for name, agent in registry.AGENTS.items():
        assert agent.name.isidentifier(), f"{name} → {agent.name}"


def test_exactly_one_agent_is_human_terminated():
    """The Escalator is the only path to a clinical decision. If a refactor
    ever makes a second agent human-terminated, or none, that is a safety
    regression and this test should fail loudly."""
    terminated = [a["displayName"] for a in registry.registry()["agents"]
                  if a["humanTerminated"]]
    assert terminated == ["Escalator"]


def test_every_agent_card_declares_model_and_scope():
    for card in registry.registry()["agents"]:
        assert card["model"].startswith("gemini-"), card
        assert card["iamScope"], card
        assert len(card["instructionHash"]) == 16


@pytest.mark.parametrize("name", ["parser", "reconciler", "escalator"])
def test_safety_language_present_in_instructions(name):
    """The agents that touch clinical judgement must carry an explicit
    do-not-decide instruction. Guards against prompt drift."""
    instruction = registry._SPEC[name][5].lower()
    assert any(p in instruction for p in
               ("do not guess", "never choose", "never resolve", "refuse")), name
