"""Reset has to survive the fleet still writing underneath it.

Firestore answers ABORTED — "Too much contention on these documents" — when a
write races other writers. It is the datastore asking to be called again.

This is not hypothetical: resetting while agents were appending to the same
patient's audit trail raised it, and with no retry it reached the browser as
"Failed to fetch" a minute before a recording. The reset button is pressed at
exactly the moment the previous run is still settling, so the race is the
normal case rather than the rare one.
"""
from __future__ import annotations

import pytest
from google.api_core import exceptions as gexc

from app.gateway.main import _retrying


def test_a_contention_error_is_retried_until_it_succeeds():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise gexc.Aborted("Too much contention on these documents.")
        return "swept"

    assert _retrying(flaky, attempts=5) == "swept"
    assert len(attempts) == 3


@pytest.mark.parametrize("err", [
    gexc.Aborted("contention"),
    gexc.ServiceUnavailable("unavailable"),
    gexc.DeadlineExceeded("deadline"),
    gexc.InternalServerError("internal"),
    gexc.TooManyRequests("rate limited"),
])
def test_every_transient_datastore_error_is_treated_as_retryable(err):
    calls = []

    def once():
        calls.append(1)
        if len(calls) == 1:
            raise err
        return "ok"

    assert _retrying(once, attempts=3) == "ok"


def test_a_real_failure_is_still_raised_rather_than_swallowed():
    """Retrying forever would turn a broken deployment into a hang. A permission
    error is not contention and must reach the caller."""
    def denied():
        raise gexc.PermissionDenied("no access to this collection")

    with pytest.raises(gexc.PermissionDenied):
        _retrying(denied, attempts=3)


def test_it_gives_up_eventually_instead_of_retrying_forever():
    calls = []

    def always_contended():
        calls.append(1)
        raise gexc.Aborted("Too much contention on these documents.")

    with pytest.raises(gexc.Aborted):
        _retrying(always_contended, attempts=3)
    assert len(calls) == 3
