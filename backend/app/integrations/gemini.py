"""Gemini client.

One place that talks to the model, so every call is timed, every failure is
typed, and swapping tiers is a config change rather than a search-and-replace.

Two tiers, both measured on this project's own extraction prompt rather than
taken from a datasheet:

    gemini-3.5-flash-lite   1.03s   extraction — high volume, structured, hot path
    gemini-3.7-flash        2.35s   judgement — ambiguity, escalate-or-not

Both caught the ticagrelor line. We use the fast one where the work is
structured extraction and the slower one only where the model is being asked to
exercise judgement, because that is the only place the extra 1.3s buys anything.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from google import genai
from google.genai import types

from ..config import settings

log = logging.getLogger("vitahome.gemini")

_client: genai.Client | None = None


class ModelError(RuntimeError):
    """A model call failed or returned something unusable.

    Raised, never swallowed: an agent that cannot parse must fail loudly so the
    task is redelivered or dead-lettered, not silently complete with no output.
    """


def client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise ModelError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_json(
    prompt: str,
    schema: dict[str, Any],
    *,
    model: str | None = None,
    image: bytes | None = None,
    mime_type: str = "image/jpeg",
    temperature: float = 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Structured generation. Returns ``(parsed, meta)``.

    ``meta`` carries the model name and wall-clock latency — the console shows
    both, because "which model, how fast" is the first thing anyone asks and the
    honest answer should already be on screen.

    Schema is enforced by the API, not by parsing prose. Temperature is 0 by
    default: this is extraction from a document, and creativity here is a defect.
    """
    mdl = model or settings.model_fast
    parts: list[Any] = []
    if image is not None:
        parts.append(types.Part.from_bytes(data=image, mime_type=mime_type))
    parts.append(types.Part.from_text(text=prompt))

    t0 = time.perf_counter()
    try:
        resp = client().models.generate_content(
            model=mdl,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
    except Exception as e:  # noqa: BLE001 — reraised as our own type
        raise ModelError(f"{mdl} call failed: {e}") from e
    ms = int((time.perf_counter() - t0) * 1000)

    text = (resp.text or "").strip()
    if not text:
        raise ModelError(f"{mdl} returned an empty response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError(f"{mdl} returned non-JSON despite a response schema: {e}") from e

    usage = getattr(resp, "usage_metadata", None)
    meta = {
        "model": mdl,
        "latencyMs": ms,
        "inputTokens": getattr(usage, "prompt_token_count", None),
        "outputTokens": getattr(usage, "candidates_token_count", None),
    }
    _meter(mdl, meta["inputTokens"], meta["outputTokens"])
    log.info("gemini model=%s ms=%s in=%s out=%s",
             mdl, ms, meta["inputTokens"], meta["outputTokens"])
    return parsed, meta


# --------------------------------------------------------------------------
# usage meter
# --------------------------------------------------------------------------
# Counting tokens rather than guessing dollars, for the same reason the Autonomy
# Ledger counts actions rather than estimating savings: a number nobody can
# check is worth less than no number. Rates change; token counts are facts the
# API reported.

_usage_lock = threading.Lock()
_usage: dict[str, dict[str, int]] = {}


def _meter(model: str, tin: int | None, tout: int | None) -> None:
    with _usage_lock:
        u = _usage.setdefault(model, {"calls": 0, "inputTokens": 0, "outputTokens": 0})
        u["calls"] += 1
        u["inputTokens"] += int(tin or 0)
        u["outputTokens"] += int(tout or 0)


def usage_report() -> dict[str, Any]:
    """Per-model totals since this instance started.

    Per-instance on purpose: it is a sanity check on what a demo run costs, not
    an accounting system. Cloud Billing is the source of truth for the bill.
    """
    with _usage_lock:
        by_model = {m: dict(v) for m, v in _usage.items()}
    return {
        "byModel": by_model,
        "totals": {
            "calls": sum(v["calls"] for v in by_model.values()),
            "inputTokens": sum(v["inputTokens"] for v in by_model.values()),
            "outputTokens": sum(v["outputTokens"] for v in by_model.values()),
        },
        "note": "tokens since this instance started — not dollars, and not billing",
    }


def ping() -> dict[str, Any]:
    """Cheap liveness check for /health/deep."""
    try:
        out, meta = generate_json(
            "Reply with {\"ok\": true}.",
            {"type": "object", "properties": {"ok": {"type": "boolean"}},
             "required": ["ok"]},
        )
        return {"ok": bool(out.get("ok")), **meta}
    except Exception as e:  # noqa: BLE001 — health checks never raise
        return {"ok": False, "error": str(e)[:200]}
