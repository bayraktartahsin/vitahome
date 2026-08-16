"""PHI and logs.

The usual design here is a redaction layer: let clinical text reach the logging
call, then scrub it on the way out. We took the other position, because
redaction-as-the-only-control fails silently — the day a pattern misses, the PHI
is in Cloud Logging, replicated, retained, and out of reach.

So the primary control is structural: **PHI is not supposed to be in a log line
at all.** Agents log references — a patient id, a task id, a step name. Pub/Sub
messages carry references. Clinical content lives in FHIR and Firestore, behind
IAM, and is fetched by the agent that needs it.

This module is the other two layers around that claim:

  1. ``PhiRedactingFilter`` — a deterministic scrub on every log record. Defence
     in depth, not the plan. It is fast, has no model in the path, and keeps
     working on a day when nothing else does.

  2. ``scan`` — Gemma reads recent log output and reports anything that looks
     like PHI got through. This is the part that makes the structural claim
     falsifiable. A control nobody audits is a belief.

Gemma rather than Gemini for the scan on purpose: it is a small open model, it
is doing pattern recognition rather than judgement, and the compliance story is
better when the thing reading your logs is the cheapest model that can do the
job rather than the most capable one available.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..config import settings

log = logging.getLogger("vitahome.compliance")

# Deterministic patterns, ordered most specific first. Each is a category a
# reviewer can name — no cleverness, nothing that needs a patient roster to
# work, and nothing that will quietly change behaviour when the data does.
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
    ("mrn", re.compile(r"\bMRN[:\s#]*\d{4,}\b", re.I), "[mrn]"),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), "[email]"),
    ("phone", re.compile(r"\b(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
     "[phone]"),
    ("dob", re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"), "[date]"),
    # The shapes a name actually arrives in: "Patient: Robert Hayes",
    # "name=Robert Hayes", and the bare "patient Robert Hayes admitted".
    # Case-insensitive, and the separator is optional — the first version of
    # this required a colon and matched none of the three.
    #
    # Two capitalised words are required after the keyword, which is what keeps
    # it off "Patient/55e38722-…" and "patient id p_hero".
    ("name",
     re.compile(r"\b(patient|name|given|family)\b\s*[:=]?\s+"
                r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", re.I),
     r"\1: [name]"),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Scrub a string. Returns ``(clean, categories_hit)``."""
    if not text:
        return text, []
    hits: list[str] = []
    out = text
    for name, pattern, replacement in _PATTERNS:
        out, n = pattern.subn(replacement, out)
        if n:
            hits.append(name)
    return out, hits


class PhiRedactingFilter(logging.Filter):
    """Scrub every log record before a handler can ship it.

    Rewrites ``record.msg`` and clears ``record.args`` after interpolation, so a
    downstream formatter cannot reconstruct the original from the arguments —
    which is the mistake that makes most redaction filters decorative.
    """

    def __init__(self, counter: dict[str, int] | None = None):
        super().__init__()
        self.counter = counter if counter is not None else {}

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:  # noqa: BLE001 — logging must never raise
            return True
        clean, hits = redact(rendered)
        if hits:
            record.msg = clean
            record.args = ()
            for h in hits:
                self.counter[h] = self.counter.get(h, 0) + 1
        return True


_counter: dict[str, int] = {}


def install() -> dict[str, int]:
    """Attach the filter to the root logger's handlers.

    On handlers rather than on the logger: a filter on a logger does not apply
    to records that propagate up from child loggers, which is most of them.
    """
    f = PhiRedactingFilter(_counter)
    root = logging.getLogger()
    for h in root.handlers:
        h.addFilter(f)
    if not root.handlers:                     # nothing configured yet
        logging.basicConfig(level=settings.log_level)
        for h in logging.getLogger().handlers:
            h.addFilter(f)
    log.info("PHI redaction filter installed on %d handler(s)", len(root.handlers))
    return _counter


def redaction_counts() -> dict[str, int]:
    return dict(_counter)


# --------------------------------------------------------------------------
# the auditor
# --------------------------------------------------------------------------

SCAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line": {"type": "string"},
                    "category": {"type": "string"},
                    "why": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["line", "category", "why", "severity"],
            },
        },
        "clean": {"type": "boolean"},
    },
    "required": ["findings", "clean"],
}

SCAN_PROMPT = """You are auditing application log lines for protected health
information that should never have been written to a log.

These logs come from a system whose stated design is that PHI never appears in
a log line at all — agents log identifiers and step names, and clinical content
stays in the clinical store. Your job is to check whether that actually held.

LOG LINES:
{lines}

Report anything that is protected health information:
- a patient's name, address, phone, email, or date of birth
- a medical record number or other direct identifier
- clinical narrative: symptoms, diagnoses, medications tied to an individual

Do NOT report:
- opaque identifiers (patient ids like p_hero or p_c0042, task ids, FHIR
  resource UUIDs). These are pseudonymous references, which is the design.
- agent names, step names, model names, latencies, counts
- drug names with no patient attached — a schedule template is not PHI
- text already redacted to a placeholder such as [name] or [mrn]

For each finding give the offending line, the category, why it qualifies, and a
severity. Set clean=true only if there are no findings at all.

Be strict about real identifiers and relaxed about opaque ones. A false positive
on a task id trains people to ignore you."""


def scan(lines: list[str]) -> dict[str, Any]:
    """Ask Gemma whether anything in these log lines is PHI."""
    from ..integrations import gemini

    if not lines:
        return {"clean": True, "findings": [], "linesScanned": 0}
    body = "\n".join(f"  {i + 1}. {ln}" for i, ln in enumerate(lines[:120]))
    out, meta = gemini.generate_json(
        SCAN_PROMPT.format(lines=body), SCAN_SCHEMA, model=settings.model_redact,
    )
    return {
        "clean": bool(out.get("clean")) and not (out.get("findings") or []),
        "findings": out.get("findings") or [],
        "linesScanned": min(len(lines), 120),
        "model": meta["model"],
        "latencyMs": meta["latencyMs"],
    }
