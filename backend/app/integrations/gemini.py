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

    # Gemma is served through the same API but does not support response_schema.
    # Asking for it yields JSON followed by whatever else the model felt like
    # saying, which then fails to parse. So it gets the shape in the prompt and
    # a tolerant reader on the way back.
    structured = "gemma" not in mdl.lower()
    if not structured:
        prompt = (f"{prompt}\n\nReply with ONE JSON object and nothing else — no "
                  f"markdown fence, no commentary. It must match this schema:\n"
                  f"{json.dumps(schema)}")
    parts.append(types.Part.from_text(text=prompt))

    cfg: dict[str, Any] = {"temperature": temperature}
    if structured:
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = schema

    t0 = time.perf_counter()
    try:
        resp = client().models.generate_content(
            model=mdl,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(**cfg),
        )
    except Exception as e:  # noqa: BLE001 — reraised as our own type
        raise ModelError(f"{mdl} call failed: {e}") from e
    ms = int((time.perf_counter() - t0) * 1000)

    text = (resp.text or "").strip()
    if not text:
        raise ModelError(f"{mdl} returned an empty response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = _first_json_object(text)
        if parsed is None:
            raise ModelError(f"{mdl} returned no parseable JSON object") from None

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


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first complete JSON object out of a noisy reply.

    Brace-matching rather than a regex, and it tracks whether it is inside a
    string so that a ``}`` in a value cannot end the object early. Needed for
    models without schema support, where the answer routinely arrives wrapped in
    a markdown fence or trailed by an explanation nobody asked for.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class VoiceUnavailable(RuntimeError):
    """Speech synthesis is not available on this key or model.

    Its own type because the caller's correct response is to fall back to text,
    not to fail the request. The Coach's question is durable either way — audio
    is a rendering of it, never the thing itself.
    """


def speak(text: str, *, voice: str = "Kore", model: str | None = None) -> tuple[bytes, str]:
    """Synthesise speech. Returns ``(pcm_bytes, mime_type)``.

    Called on demand rather than at check-in time: the question is written once
    and read aloud only if somebody presses play, so an unheard check-in costs
    nothing.
    """
    mdl = model or settings.model_tts
    try:
        resp = client().models.generate_content(
            model=mdl,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )
    except Exception as e:  # noqa: BLE001
        raise VoiceUnavailable(f"{mdl}: {e}") from e

    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                _meter(mdl, None, None)
                return inline.data, inline.mime_type or "audio/L16;rate=24000"
    raise VoiceUnavailable(f"{mdl} returned no audio")


def pcm_to_wav(pcm: bytes, mime: str) -> bytes:
    """Wrap raw PCM in a WAV header.

    The API returns headerless signed 16-bit little-endian PCM; browsers will
    not play that. Sample rate is parsed from the mime type rather than assumed,
    because getting it wrong produces audio at the wrong pitch — which sounds
    like a broken product rather than a wrong constant.
    """
    import io
    import re
    import wave

    rate = int(m.group(1)) if (m := re.search(r"rate=(\d+)", mime or "")) else 24000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)          # L16
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


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
