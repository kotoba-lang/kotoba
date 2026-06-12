"""Image generation client for murakumo (OpenAI-compatible /v1/images/generations)."""

from __future__ import annotations

import base64
import logging
import os

import httpx

_log = logging.getLogger(__name__)

_DEFAULT_IMAGE_URL = os.environ.get(
    "MURAKUMO_IMAGE_URL",
    "https://vyp99t9px7h4dl-4000.proxy.runpod.net/v1/images/generations",
)
_TIMEOUT = float(os.environ.get("IMAGE_TIMEOUT_SEC", "60"))


async def generate_background(
    location: str,
    action: str = "",
    image_url: str = "",
) -> bytes | None:
    """Generate a background image via murakumo flux-schnell.

    Returns PNG bytes or None (use gradient fallback when None).
    """
    url = (image_url or _DEFAULT_IMAGE_URL).rstrip("/")
    prompt = f"anime background, {location}, {action}, soft lighting, 16:9, no characters"
    payload = {
        "model": "flux-schnell",
        "prompt": prompt,
        "n": 1,
        "size": "1280x720",
        "response_format": "b64_json",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(url, json=payload)
        if r.status_code == 200:
            data = r.json()
            b64 = (data.get("data") or [{}])[0].get("b64_json") or ""
            if b64:
                return base64.b64decode(b64)
        _log.warning("image gen %s returned %d: %s", url, r.status_code, r.text[:200])
    except Exception as exc:
        _log.warning("image gen failed: %s", exc)
    return None
