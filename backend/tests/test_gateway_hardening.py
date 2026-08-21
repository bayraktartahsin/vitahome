"""The public surface has to refuse bad input, not fall over on it.

The chaos panel is deliberately open so judges can drive it themselves, which
means every query string and body on this deployment is untrusted. A 4xx is a
correct answer to a bad request; a 5xx is an unhandled exception reaching a
reviewer, and it reads as a crash whether or not the demo path still works.

Each case here was a real 500 found by scripts/hardening.py.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.gateway.main import MAX_DOCUMENT_CHARS, _clean_pid


@pytest.mark.parametrize("pid", [
    "x" * 5000,          # Firestore rejects an id over 1500 bytes
    "a/b",               # a slash addresses a subcollection, not a document
    "../../etc/passwd",  # traversal-shaped input
    "",
])
def test_a_patient_id_that_firestore_would_choke_on_is_refused_at_the_door(pid):
    with pytest.raises(HTTPException) as e:
        _clean_pid(pid)
    assert e.value.status_code == 400


@pytest.mark.parametrize("pid", ["p_hero", "p_c0042", "patient-1"])
def test_ordinary_patient_ids_still_pass(pid):
    assert _clean_pid(pid) == pid


def test_the_document_cap_is_generous_but_finite():
    """A discharge summary is one or two pages. Without a cap, a pasted corpus
    made the model call hang and the request returned nothing at all — worse
    for a reviewer than being told no."""
    assert 5_000 < MAX_DOCUMENT_CHARS < 100_000
