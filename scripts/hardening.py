#!/usr/bin/env python3
"""Adversarial sweep of every surface a judge can reach.

The demo is public and the chaos panel is deliberately open, so a judge is
invited to poke at it. This asks the question that matters before that happens:
does anything here answer a bad request with a stack trace?

A 4xx is a correct answer to a bad input. A 5xx is the failure this looks for —
it means an unhandled exception reached the client, and on a judged deployment
that is a crash whether or not the demo path still works.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys

import httpx

GATEWAY = "https://vitahome-gateway-205100594497.us-central1.run.app"
WEB = "https://vitahome.vitamedas.com"

results: list[tuple[str, str, int, str]] = []


def check(kind: str, method: str, url: str, *, expect=(200,), json_body=None,
          note: str = "") -> None:
    try:
        r = httpx.request(method, url, json=json_body, timeout=90.0,
                          follow_redirects=True)
        code = r.status_code
    except Exception as e:                      # noqa: BLE001 — reporting tool
        results.append((kind, f"{method} {url}", 0, f"NO RESPONSE: {e}"))
        return
    ok = code in expect
    detail = "" if ok else r.text[:110].replace("\n", " ")
    results.append((kind, f"{method} {url.replace(GATEWAY,'').replace(WEB,'')}",
                    code, detail if not ok else note))


PAGES = ["/", "/capture", "/console", "/console/drill", "/console/fleets",
         "/today", "/director", "/architecture"]

# (method, path, expected statuses) — anything outside the expected set is
# reported, and any 5xx is a failure regardless of what was expected.
READS = [
    ("GET", "/health", (200,)),
    # note: /healthz is answered by Cloud Run's own frontend before it
    # reaches the app, so it is not ours to serve and is not advertised.
    ("GET", "/health/deep", (200,)),
    ("GET", "/registry", (200,)),
    ("GET", "/demo/calendar", (200,)),
    ("GET", "/demo/calendar/list", (200,)),
    ("GET", "/demo/calendar/events", (200,)),
    ("GET", "/demo/document", (200,)),
    ("GET", "/demo/scenarios", (200,)),
    ("GET", "/patient/p_hero/plan", (200,)),
    ("GET", "/patient/p_hero/ledger", (200,)),
    ("GET", "/patient/p_hero/tasks", (200,)),
    ("GET", "/patient/p_hero/audit?limit=10", (200,)),
    ("GET", "/patient/p_hero/exceptions", (200,)),
    ("GET", "/chaos/status", (200,)),
]

# Deliberately hostile or malformed. None of these may produce a 5xx.
ABUSE = [
    ("GET", "/patient/does_not_exist/plan", (200, 404)),
    ("GET", "/patient/does_not_exist/ledger", (200, 404)),
    ("GET", "/patient/does_not_exist/audit", (200, 404)),
    ("GET", "/patient/does_not_exist/exceptions", (200, 404)),
    ("GET", "/patient/..%2F..%2Fetc%2Fpasswd/plan", (200, 400, 404)),
    ("GET", "/patient/p_hero/audit?limit=-5", (200, 422)),
    ("GET", "/patient/p_hero/audit?limit=999999", (200, 422)),
    ("GET", "/patient/p_hero/audit?limit=abc", (422,)),
    ("GET", "/patient/p_hero/task/nope/anything", (404, 405)),
    ("POST", "/demo/dispatch", (404, 422)),
    ("POST", "/demo/observe?scenario=not_a_scenario&patientId=p_hero", (200, 400, 404)),
    ("POST", "/demo/observe?scenario=chest_pain&patientId=ghost", (200, 400, 404)),
    ("POST", "/demo/book-followups?patientId=ghost", (200, 404)),
    ("POST", "/chaos/arm?agent=not_an_agent&patientId=p_hero&step=x", (200, 400, 404)),
    ("POST", "/demo/cohort?count=-1", (200, 400, 422)),
    ("POST", "/demo/cohort?count=99999999", (200, 400, 422)),
    ("POST", "/demo/storm?count=-3", (200, 400, 422)),
    ("GET", "/health/deep?back=https://evil.com/x", (200,)),
    ("GET", "/nope/not/a/route", (404,)),
]

print("pages")
with cf.ThreadPoolExecutor(8) as pool:
    list(pool.map(lambda p: check("page", "GET", WEB + p), PAGES))

print("read endpoints")
with cf.ThreadPoolExecutor(8) as pool:
    list(pool.map(lambda t: check("read", t[0], GATEWAY + t[1], expect=t[2]), READS))

print("malformed and hostile input")
for m, path, exp in ABUSE:
    check("abuse", m, GATEWAY + path, expect=exp)

# Bodies that are the wrong shape entirely.
print("bad bodies")
for body, exp in [
    ({}, (200, 404, 422)),
    ({"patientId": "p_hero", "agent": "nope"}, (404,)),
    ({"patientId": None, "agent": "scheduler"}, (200, 404, 422)),
    ({"patientId": "p_hero", "agent": "scheduler", "payload": "not-an-object"}, (200, 422)),
    ({"patientId": "x" * 5000, "agent": "scheduler"}, (200, 400, 404, 422)),
]:
    check("body", "POST", GATEWAY + "/demo/dispatch", expect=exp, json_body=body)

print("parser with hostile documents")
for text, exp in [
    ("", (400, 422)),
    ("   ", (400, 422)),
    ("Buy cheap shoes. This is not a medical document at all.", (200,)),
    ("<script>alert(1)</script>" * 40, (200, 400, 422)),
    ("A" * 60000, (200, 400, 413, 422)),
]:
    check("parser", "POST", GATEWAY + "/capture", expect=exp,
          json_body={"patientId": "p_hero", "documentText": text})

# ---------------------------------------------------------------- report ----
print()
fails = [r for r in results if r[2] >= 500 or r[2] == 0]
odd = [r for r in results if r not in fails and r[3] and r[2] not in (200,)]

for kind, what, code, detail in results:
    mark = "FAIL" if (code >= 500 or code == 0) else "ok  "
    if mark == "FAIL" or detail:
        print(f"  {mark} {code:>4}  {what[:74]}  {detail[:60]}")

print()
print(f"  checked {len(results)} requests")
print(f"  5xx / no-response: {len(fails)}")
if fails:
    print("\n  CRASHES:")
    for kind, what, code, detail in fails:
        print(f"    {code}  {what}  {detail}")
    sys.exit(1)
print("  no endpoint answered with a server error")
