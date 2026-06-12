"""TTS client for murakumo kokoro provider (OpenAI-compatible /v1/audio/speech)."""

from __future__ import annotations

import logging
import os

import httpx

_log = logging.getLogger(__name__)

_VOICE_MAP = {
    "left": "af_heart",
    "right": "am_puck",
}

_DEFAULT_TTS_URL = os.environ.get(
    "MURAKUMO_TTS_URL",
    "https://vyp99t9px7h4dl-4000.proxy.runpod.net/v1/audio/speech",
)
_TIMEOUT = float(os.environ.get("TTS_TIMEOUT_SEC", "30"))


async def synthesize(
    text: str,
    speaker: str,
    tts_url: str = "",
    speed: float = 1.0,
) -> bytes | None:
    """Call murakumo kokoro TTS. Returns WAV bytes or None on failure.

    Args:
        text: Japanese dialogue text
        speaker: "left" (af_heart) or "right" (am_puck)
        tts_url: override endpoint (falls back to MURAKUMO_TTS_URL env)
        speed: speech speed multiplier
    """
    url = (tts_url or _DEFAULT_TTS_URL).rstrip("/")
    voice = _VOICE_MAP.get(speaker, "af_heart")
    payload = {
        "model": "kokoro",
        "input": text,
        "voice": voice,
        "response_format": "wav",
        "speed": speed,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(url, json=payload)
        if r.status_code == 200:
            return r.content
        _log.warning("TTS %s returned %d: %s", url, r.status_code, r.text[:200])
    except Exception as exc:
        _log.warning("TTS failed: %s", exc)
    return None
