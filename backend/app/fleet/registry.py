"""Agent registry — served as A2A agent cards at GET /registry.

The Fortified Enterprise Fleet track requires an "agent registry". This is it,
at a URL, versioned, with each agent's capabilities, model, and IAM scope.
Agents are declared as ADK Agent objects so the topology is inspectable in the
framework's own types, not just ours.
"""
from __future__ import annotations

import hashlib
from typing import Any

from google.adk.agents import Agent

from ..config import settings

FLEET_VERSION = "0.1.0"

# name -> (glyph, verb, one-line duty, model, iam scope, instruction)
_SPEC: dict[str, tuple[str, str, str, str, str, str]] = {
    # The model on each card is the model the agent actually calls. An A2A card
    # is a contract a reviewer can check against /capture's reported model — two
    # of these used to disagree with the code, which is worse than not
    # publishing the field at all. tests/test_fleet_contracts.py holds the line.
    "parser": ("📄", "reads", "Turns a photographed medical document into a structured plan and ranks each instruction by how dangerous it is to miss.",
               settings.model_fast, "healthcare.fhirResources.create",
               "You read medical instruction documents. Extract every instruction verbatim with its line number. "
               "Rank criticality: CRITICAL means a patient could die if this is missed. Never invent an instruction. "
               "If a line is ambiguous or illegible, mark low confidence — do not guess."),
    "reconciler": ("💊", "checks", "Compares new medications against the patient's existing list and flags interactions, duplications and stops.",
                   settings.model_reason, "healthcare.fhirResources.get",
                   "You reconcile medication lists. Identify what starts, what stops, what conflicts. "
                   "If an instruction has two plausible readings, you REFUSE to act and escalate with the options. "
                   "You never choose between clinical alternatives yourself."),
    "scheduler": ("📅", "books", "Books every follow-up appointment the document requires.",
                  settings.model_fast, "healthcare.fhirResources.create + calendar.events.create",
                  "You book follow-up appointments from discharge instructions. Respect the stated interval."),
    "pharmacist": ("🏥", "sends", "Routes prescriptions and builds the dose schedule.",
                   settings.model_fast, "healthcare.fhirResources.update",
                   "You route prescriptions and construct dose schedules. You never alter a dose."),
    "watchman": ("👁", "watches", "Monitors for the red-flag symptoms named in THIS document, 24/7.",
                 settings.model_reason, "healthcare.fhirResources.create",
                 "You watch incoming observations against this document's specific red-flag list. "
                 "You do not diagnose. You match and you raise."),
    "coach": ("🗣", "checks in", "Runs adaptive daily check-ins by voice and feeds answers back to the fleet.",
              settings.model_reason, "none",
              "You check in with a recovering patient once a day, warmly and briefly. Ask ONE question, "
              "chosen from what the fleet most needs to know today. Never give medical advice."),
    "escalator": ("🚨", "calls a human", "Decides when a licensed human must be involved — and is the only path to a clinical decision.",
                  settings.model_reason, "healthcare.fhirResources.create",
                  "You decide whether a licensed clinician must be paged. You assemble the context pack. "
                  "You never resolve a clinical question yourself — you route it. Deciding NOT to page is also "
                  "a decision you log, with your reasoning."),
}


def build_agent(name: str) -> Agent:
    glyph, verb, duty, model, _scope, instruction = _SPEC[name]
    return Agent(
        name=f"vitahome_{name}",
        description=f"{glyph} {name} — {verb}. {duty}",
        model=model,
        instruction=instruction,
    )


AGENTS: dict[str, Agent] = {n: build_agent(n) for n in _SPEC}


def agent_card(name: str) -> dict[str, Any]:
    """A2A-style agent card."""
    glyph, verb, duty, model, scope, instruction = _SPEC[name]
    return {
        "name": f"vitahome_{name}",
        "displayName": name.capitalize(),
        "glyph": glyph,
        "verb": verb,
        "description": duty,
        "version": FLEET_VERSION,
        "model": model,
        "iamScope": scope,
        "instructionHash": hashlib.sha256(instruction.encode()).hexdigest()[:16],
        "endpoint": f"/agents/{name}",
        # The physical service this agent runs on. "gateway" unless it has been
        # extracted — which is a push-endpoint change, and this field is how a
        # reviewer verifies that claim rather than taking it on faith.
        "service": settings.agent_service_map.get(name, "gateway"),
        "transport": "pubsub-push",
        "humanTerminated": name == "escalator",
    }


def registry() -> dict[str, Any]:
    return {
        "fleet": "vitahome",
        "version": FLEET_VERSION,
        "protocol": "a2a-agent-card/v1",
        "agents": [agent_card(n) for n in _SPEC],
    }
