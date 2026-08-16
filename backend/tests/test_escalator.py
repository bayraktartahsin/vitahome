"""Escalator — the safety asymmetry.

The Escalator is allowed to decide a human is not needed. That is the whole
point of it: a monitor that pages for everything gets ignored, and an ignored
monitor is worse than none because it creates a false belief that someone is
watching.

Restraint is only shippable if it cannot be turned into silence. So the code is
permitted to override the model in exactly one direction — toward paging, never
away from it. Every test below exists to hold that line. If someone later
"simplifies" the hard override away, these fail.
"""
from __future__ import annotations

import pytest

from app.agents import escalator
from app.fleet.runtime import Escalation, Refusal


@pytest.fixture
def run(monkeypatch):
    """Drive body() with a canned model verdict and capture audit lines."""

    def _go(recommend: bool, urgency: str = "urgent", **assessment):
        audits: list[tuple] = []
        monkeypatch.setattr(escalator.ledger, "audit",
                            lambda *a, **k: audits.append((a, k)))
        monkeypatch.setattr(
            escalator.ledger, "run_step",
            lambda pid, tid, agent, name, fn: fn(f"{tid}:{name}"),
        )
        monkeypatch.setattr(
            escalator.gemini, "generate_json",
            lambda *a, **k: ({
                "recommendEscalation": recommend,
                "urgency": urgency,
                "rationale": assessment.get("rationale", "because"),
                "argumentsAgainst": assessment.get("argumentsAgainst", "the other side"),
                "whatWouldChangeThis": assessment.get("whatWouldChangeThis", "a new symptom"),
            }, {"model": "gemini-3.7-flash", "latencyMs": 2100}),
        )
        return audits

    return _go


def _task(**inp):
    base = {"finding": "reported symptom", "observation": "something happened",
            "matchedFlags": []}
    return {"input": {**base, **inp}}


# ------------------------------------------------- the asymmetry (load-bearing)

def test_model_reassurance_cannot_suppress_a_documented_red_flag(run):
    """THE test. The model says stand down; the symptom is printed on the
    patient's own return-to-emergency list. It escalates anyway."""
    run(recommend=False, urgency="none")
    with pytest.raises(Escalation) as e:
        escalator.body("p", "t", _task(
            observation="heavy chest pain for twenty minutes, sitting down",
            matchedFlags=["chest pain"],
        ))
    assert e.value.context["hardOverride"] is True
    assert e.value.context["urgency"] == "emergency"


def test_the_override_fires_on_the_raw_report_not_only_the_matched_list(run):
    """If the matcher upstream missed it, the words still count. Two independent
    chances to catch the same thing, on purpose."""
    run(recommend=False, urgency="none")
    with pytest.raises(Escalation) as e:
        escalator.body("p", "t", _task(
            observation="he fainted in the kitchen", matchedFlags=[]))
    assert e.value.context["hardOverride"] is True


def test_an_override_is_recorded_as_a_disagreement_not_hidden(run):
    """When code overrules the model, that has to be visible in the audit trail.
    Silently correcting a model is how you lose track of how often it is wrong."""
    audits = run(recommend=False, urgency="none")
    with pytest.raises(Escalation):
        escalator.body("p", "t", _task(observation="bleeding from the site",
                                       matchedFlags=["bleeding"]))
    overrides = [a for a in audits if a[1].get("extra", {}).get("hardOverride")
                 or (len(a[0]) > 3 and "overridden" in str(a[0][3]))]
    assert overrides, "the override was not written to the audit trail"


def test_code_never_overrides_toward_silence(run):
    """The asymmetry, stated as its own test: the model recommending escalation
    is always sufficient. There is no path where code cancels a page."""
    run(recommend=True, urgency="routine")
    with pytest.raises(Escalation) as e:
        escalator.body("p", "t", _task(observation="mild ankle swelling"))
    assert e.value.context["hardOverride"] is False


# --------------------------------------------------------------- the restraint

def test_it_can_decide_a_human_is_not_needed(run):
    """The counter-beat. Nothing on the red-flag list, model says stand down."""
    run(recommend=False, urgency="none")
    summary = escalator.body("p", "t", _task(
        observation="heart rate 104 after the stairs, back to 72 within two minutes, "
                    "no chest pain, no dizziness",
        matchedFlags=[],
    ))
    assert "no human needed" in summary


def test_standing_down_records_what_would_have_changed_the_answer(run):
    """A decision not to act must be as auditable as a decision to act, or no
    one can review it afterwards."""
    audits = run(recommend=False, urgency="none",
                 rationale="expected on beta-blocker titration, resolved at rest",
                 whatWouldChangeThis="any chest pain, or a rate that does not settle")
    escalator.body("p", "t", _task(observation="fast pulse on the stairs"))
    stand_downs = [a for a in audits if "stood down" in str(a[0])]
    assert stand_downs, "standing down left no audit entry"
    extra = stand_downs[0][0][5] if len(stand_downs[0][0]) > 5 else stand_downs[0][1]
    assert "whatWouldChangeThis" in str(extra)


# ------------------------------------------------------------------- contract

def test_escalation_carries_the_case_against_itself(run):
    """argumentsAgainst travels with the page. The clinician being woken should
    see the strongest reason this might be nothing, not just the alarm."""
    run(recommend=True, urgency="urgent",
        argumentsAgainst="symptom resolved before the call")
    with pytest.raises(Escalation) as e:
        escalator.body("p", "t", _task(observation="palpitations earlier today"))
    assert e.value.context["argumentsAgainst"] == "symptom resolved before the call"


def test_an_sla_is_attached_to_every_page(run):
    run(recommend=True, urgency="urgent")
    with pytest.raises(Escalation) as e:
        escalator.body("p", "t", _task(observation="palpitations"))
    assert e.value.context["slaMinutes"] == 30


def test_emergency_override_gets_the_tightest_sla(run):
    run(recommend=False, urgency="none")
    with pytest.raises(Escalation) as e:
        escalator.body("p", "t", _task(observation="chest pain", matchedFlags=["chest pain"]))
    assert e.value.context["slaMinutes"] == 5


def test_nothing_to_assess_refuses_rather_than_standing_down(run):
    """An empty finding is a broken upstream, not a reassuring result. Refusing
    is right; reporting 'no human needed' would be a lie."""
    run(recommend=False)
    with pytest.raises(Refusal):
        escalator.body("p", "t", {"input": {}})


# -------------------------------------------------------- the override itself

@pytest.mark.parametrize("text", [
    "CHEST PAIN", "he has chest pain", "Shortness of breath at rest",
    "bleeding from the groin site", "brief fainting episode",
])
def test_override_terms_match_case_insensitively(text):
    assert escalator._hard_override([], text) is not None


@pytest.mark.parametrize("text", [
    "heart rate 104 on the stairs, resolved at rest",
    "mild bruising at the wrist",
    "slept badly",
    "his blood pressure was 118 over 76",          # 'blood' must not fire
    "he is on a blood thinner and tolerating it",
    "breathing normally, colour is good",          # 'breath' must not fire
])
def test_benign_reports_do_not_trip_the_override(text):
    assert escalator._hard_override([], text) is None


# ---------------------------------------------------------------- negation
# Home reports rule things out constantly: "no chest pain, no dizziness" is how
# a careful family member describes something reassuring. Reading those as
# positive findings would page a clinician for every calm message — which makes
# the restraint case impossible and the alerting worthless.

@pytest.mark.parametrize("text", [
    "no chest pain, no dizziness, no shortness of breath",
    "he denies chest pain",
    "she has not fainted",
    "no bleeding at the site",
    "feels fine, without any chest pain",
    "hasn't passed out at all",
])
def test_denied_symptoms_do_not_force_escalation(text):
    assert escalator._hard_override([], text) is None, f"negation missed in: {text}"


@pytest.mark.parametrize("text", [
    "no dizziness, but he does have chest pain",
    "no nausea; bleeding from the wrist site",
    "not eating much and he fainted this morning",
])
def test_a_denial_of_one_symptom_does_not_cover_the_next(text):
    """The expensive direction of wrong. 'No X, but Y' must still escalate on Y."""
    assert escalator._hard_override([], text) is not None, f"missed real symptom in: {text}"


def test_the_restraint_scenario_does_not_trip_the_override():
    """Pinned against the actual demo text. If this ever fails, the counter-beat
    escalates on camera and the point of the whole segment is lost."""
    from app.sim import vitals
    sc = vitals.scenario("exertional_tachycardia")
    assert escalator._hard_override([], sc["observation"]) is None


def test_the_escalation_scenario_does_trip_the_override():
    from app.sim import vitals
    sc = vitals.scenario("chest_pain")
    assert escalator._hard_override([], sc["observation"]) is not None
