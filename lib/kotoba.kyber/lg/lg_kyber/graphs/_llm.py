"""Guarded LLM caller for lg-kyber graphs.

Priority:
  1. Murakumo fleet (MURAKUMO_BASE_URL / gemma-4-e4b-it)
  2. OpenRouter (OPENROUTER_API_KEY)

Returns (parsed_json_or_None, source_label).
Falls back to deterministic path on missing key / network error / non-JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
import urllib.parse
from typing import Any

_log = logging.getLogger(__name__)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def call_llm_json(
    prompt: str,
    *,
    max_tokens: int = 200,
    model_murakumo: str = "gemma-4-e4b-it",
    model_openrouter: str = "anthropic/claude-haiku-4",
) -> tuple[dict[str, Any] | None, str]:
    base = os.environ.get("MURAKUMO_BASE_URL", "https://murakumo.etzhayyim.com")
    try:
        meta_req = urllib.request.Request(f"{base}/_app/meta")
        with urllib.request.urlopen(meta_req, timeout=5) as r:
            meta = json.loads(r.read().decode())
        if (meta.get("fleet") or {}).get("healthPct", -1) == 0:
            raise RuntimeError("fleet offline")
        resp = _post_json(
            f"{base}/api/openai/v1/chat/completions",
            {
                "model": model_murakumo,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            {"content-type": "application/json", "x-kotodama-verified": "true"},
        )
        content = resp["choices"][0]["message"]["content"]
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        return json.loads(content), "llm"
    except Exception as e:
        _log.debug("[kyber._llm] murakumo failed: %s", e)

    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        try:
            resp = _post_json(
                "https://openrouter.ai/api/v1/chat/completions",
                {
                    "model": model_openrouter,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
                {
                    "authorization": f"Bearer {key}",
                    "content-type": "application/json",
                    "http-referer": "https://kyber.etzhayyim.com",
                    "x-title": "lg-kyber",
                },
            )
            content = resp["choices"][0]["message"]["content"]
            return json.loads(content), "llm"
        except Exception as e:
            _log.debug("[kyber._llm] openrouter failed: %s", e)

    return None, "deterministic"
