"""Credential handling under concurrency.

This exists because of a live failure: seeding two hundred cohort patients
across sixteen threads produced 189 successes and 11 bare 401s. The cause was
not the API — it was several threads refreshing the same credential object at
once, with one of them reading the token mid-swap.

Agents run concurrently on Cloud Run, so this was never a seeding-only bug. It
just needed volume to become visible.
"""
from __future__ import annotations

import threading
import time

import pytest

from app.integrations import fhir


class _Cred:
    """A credential whose refresh has a window — like the real one.

    ``token`` is deliberately blanked while refreshing, which is what a reader
    without a lock can observe.
    """

    def __init__(self, refresh_seconds: float = 0.02):
        self.token = "tok-0"
        self.valid = False
        self.refreshes = 0
        self._n = 0
        self._delay = refresh_seconds

    def refresh(self, _request):
        self.refreshes += 1
        self.token = ""              # the window a racing reader can see
        time.sleep(self._delay)
        self._n += 1
        self.token = f"tok-{self._n}"
        self.valid = True


@pytest.fixture
def cred(monkeypatch):
    c = _Cred()
    monkeypatch.setattr(fhir, "_creds", c)
    monkeypatch.setattr(fhir, "_creds_lock", threading.Lock())
    monkeypatch.setattr(fhir.google.auth.transport.requests, "Request", lambda: object())
    return c


def _hammer(n: int = 16) -> list[str]:
    out: list[str] = []
    lock = threading.Lock()

    def grab():
        t = fhir._token()
        with lock:
            out.append(t)

    threads = [threading.Thread(target=grab) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def test_simultaneous_callers_trigger_exactly_one_refresh(cred):
    """The load-bearing assertion — this is the one that fails without the lock.

    Sixteen threads observing an expired credential each called refresh(), so
    sixteen concurrent renewals hit the metadata server against a credential
    object that google-auth does not document as thread-safe. Some of those
    came back unusable, which is where the 401s came from.
    """
    _hammer(16)
    assert cred.refreshes == 1, f"{cred.refreshes} concurrent refreshes"


def test_no_thread_ever_receives_a_token_mid_refresh(cred):
    """The other half of the same guarantee: the read and the refresh are not
    interleaved, so nobody can observe the credential half-swapped.

    Unlike the test above this one is timing-dependent — with the lock removed
    it fails only sometimes, because the window is narrow. Kept because it
    states the property directly; the refresh-count test is what actually
    holds the line.
    """
    tokens = _hammer(16)
    assert len(tokens) == 16
    assert all(t for t in tokens), "a thread received an empty token during a refresh"


def test_a_valid_credential_is_not_refreshed_again(cred):
    fhir._token()
    before = cred.refreshes
    _hammer(8)
    assert cred.refreshes == before


def test_headers_carry_the_token_and_fhir_content_type(cred):
    h = fhir._headers()
    assert h["Authorization"].startswith("Bearer tok-")
    assert h["Content-Type"] == "application/fhir+json"
