"""Home monitoring feed — declared simulation.

There is no wearable on this patient's wrist. These are the reports a home
monitor or a family member would send, and the console labels them
"simulated home monitor" wherever they appear. Judges forgive declared
simulation; they never forgive discovered simulation.

Three scenarios, because there are three outcomes worth showing and only one of
them is the easy one:

  chest_pain               paged. Anything can be built to do this.
  lightheaded_on_standing  reaches the Escalator, and the Escalator declines.
                           Restraint as an explicit, reasoned decision.
  exertional_tachycardia   never reaches the Escalator at all — the Watchman
                           records it and matches nothing. Restraint by not
                           generating an alert in the first place.

The last two are different mechanisms and both matter. A system that only has
the first kind of restraint still floods the queue; a system that only has the
second kind cannot explain itself.

The scenarios are written as a family member would actually report — vague,
partial, with the reassuring detail buried mid-sentence — not as clean
structured vitals. Cleaning them up first would be quietly doing the hard part
by hand.
"""
from __future__ import annotations

from typing import Any

SCENARIOS: dict[str, dict[str, Any]] = {
    "chest_pain": {
        "label": "Chest pain at rest",
        "expect": "escalate",
        "observation": (
            "Dad says he's had a heavy feeling in his chest for about twenty "
            "minutes. He's sitting down. He says it's not as bad as the pain he "
            "had before the stent but it hasn't gone away. Slightly short of breath."
        ),
        "context": "post-PCI day 3 at home, on aspirin + ticagrelor",
        "note": "Matches two items on his printed return-to-emergency list.",
    },
    "lightheaded_on_standing": {
        "label": "Lightheaded when he stands up",
        "expect": "stand down",
        "observation": (
            "He's been a bit lightheaded when he stands up quickly, the last two "
            "days. It passes after a few seconds if he waits. He hasn't fallen and "
            "hasn't passed out. No chest pain. He's eating and walking around the "
            "house fine. I just wasn't sure whether to call someone."
        ),
        "context": (
            "post-PCI day 3 at home; started metoprolol 25 mg on discharge and there "
            "is an unresolved question about whether amlodipine was stopped — if he "
            "is taking both, a drop in blood pressure on standing is exactly what "
            "you would expect. Cardiology follow-up is already booked for day 7."
        ),
        "note": (
            "The restraint beat. Matches nothing on the printed red-flag list, so "
            "no hard override applies — but it is worth a clinician's eye, so the "
            "Watchman routes it and the Escalator makes an explicit decision NOT to "
            "page, recording what would have changed its answer.\n\n"
            "It also closes the loop on the Reconciler's refusal: the medication "
            "question a human was asked to settle is now showing up as a symptom. "
            "That is not decoration — an unresolved decision having downstream "
            "consequences is the honest reason refusals need an SLA too."
        ),
    },
    "exertional_tachycardia": {
        "label": "Fast heart rate on the stairs",
        "expect": "stand down",
        "observation": (
            "His watch said 104 beats per minute after he walked up the stairs. "
            "He sat down and it came back to 72 within about two minutes. No chest "
            "pain, no dizziness, no shortness of breath. He says he feels fine."
        ),
        "context": (
            "post-PCI day 3 at home, started metoprolol 25 mg on discharge; "
            "a rate of 104 on exertion resolving promptly at rest is expected "
            "during beta-blocker titration"
        ),
        "note": "Matches nothing on the return-to-emergency list. This is the restraint case.",
    },
}


def scenario(name: str) -> dict[str, Any]:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario '{name}' — have {sorted(SCENARIOS)}")
    return {**SCENARIOS[name], "id": name, "source": "simulated home monitor"}
