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


# --------------------------------------------------------- the armed drill

def test_the_arm_can_target_a_specific_step(monkeypatch):
    """Without a target the arm fires on whichever step runs first, which for
    the Scheduler is step one of three. The task then dies before anything has
    completed and the replay has nothing to skip — so three perfect-looking
    drill runs demonstrated redelivery and never once demonstrated the property
    the drill exists to prove."""
    from app.fleet import chaos

    monkeypatch.setattr(chaos, "armed",
                        lambda: {"agent": "scheduler", "step": "fhir_appointment"})
    # An earlier step must be allowed to complete...
    assert chaos.consume_if_armed("scheduler", "p", "t", "resolve_provider") is False
    # ...and a different agent is never affected.
    assert chaos.consume_if_armed("watchman", "p", "t", "fhir_appointment") is False


def test_an_untargeted_arm_still_fires_on_the_first_step(monkeypatch):
    """The old behaviour stays available — it is the right one for an agent
    whose steps you do not know."""
    from app.fleet import chaos
    monkeypatch.setattr(chaos, "armed", lambda: {"agent": "scheduler", "step": None})
    killed = {}
    monkeypatch.setattr(chaos, "_doc", lambda: type("D", (), {"delete": lambda s: None})())
    monkeypatch.setattr(chaos, "audit", lambda *a, **k: None)
    monkeypatch.setattr(chaos.os, "_exit", lambda code: killed.setdefault("code", code))
    chaos.consume_if_armed("scheduler", "p", "t", "resolve_provider")
    assert killed["code"] == 1


def test_every_agent_card_names_the_model_that_agent_actually_calls():
    """An A2A card is a contract a reviewer can check.

    /capture reports the model it just used, and /registry publishes one per
    agent — so the two being different is not a cosmetic slip, it is the
    published contract disagreeing with the running code. Two cards did drift
    this way (the Parser claimed the reasoning model while calling the fast one;
    the Watchman the reverse), which is why this reads the source rather than
    trusting the table.
    """
    import re
    from pathlib import Path

    from app.config import settings

    agents_dir = Path(__file__).resolve().parent.parent / "app" / "agents"
    tier = {settings.model_fast: "fast", settings.model_reason: "reason"}

    for name, card in ((n, registry.agent_card(n)) for n in registry._SPEC):
        src = (agents_dir / f"{name}.py").read_text()
        used = set(re.findall(r"model=settings\.model_(fast|reason)", src))
        if not used:
            continue          # deterministic agent — nothing to disagree about
        assert len(used) == 1, f"{name} calls more than one model tier: {used}"
        assert tier[card["model"]] == used.pop(), (
            f"{name}'s agent card advertises {card['model']}, "
            f"which is not the model {name}.py calls"
        )
