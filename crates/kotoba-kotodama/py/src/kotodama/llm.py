"""
ADR-0050 — Shared LLM tier abstraction.

Handlers (classify_t3, shinka compose_content, mangaka storyboard, …) should
not hard-code Vultr Serverless model IDs. They call `llm.call_tier("fast",
system=..., user=...)` and this module picks the current best model per tier,
wraps the HTTP call, strips Markdown code fences, and returns a parsed dict
so each handler's core logic stays readable.

Tier mapping (2026-04-28 — routed via llm.etzhayyim.com → murakumo-serve.etzhayyim.com LiteLLM):

| Tier         | Model (murakumo alias)  | Backend            | Why |
|--------------|-------------------------|--------------------|-----|
| fast         | `tier0-general`         | gemma-4-e2b-it     | Light general tasks. No reasoning tail. |
| mid          | `tier0-general`         | gemma-4-e2b-it     | Same as fast — balances speed/quality. |
| classifier   | `tier0-structured`      | gemma-4-e4b-it     | Structured JSON classifiers. |
| structured   | `tier0-structured`      | gemma-4-e4b-it     | Any call needing clean JSON back. |
| deep         | `tier0-structured`      | gemma-4-e4b-it     | Complex extraction (prev. Kimi-K2.6). |
| reasoning    | (Vultr direct, no override) | Qwen3.5-397B  | Reserved for long reasoning chains. |
| frontier     | (Vultr direct, no override) | Kimi-K2.6     | Long-context tasks. |

See `classify_t3.py` for why reasoning models are a poor fit for sub-100-tok
structured outputs: their chain-of-thought eats the max_tokens budget before
the model emits the JSON answer.

This module does NOT touch the database. Handlers remain responsible for
INSERT / SELECT. Keep the module stateless + import-time cheap.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Literal

_ENDPOINT = "https://api.vultrinference.com/v1/chat/completions"
_KEY_ENV = "VULTR_SERVERLESS_KEY"

# ADR-2604231328 — per-tier endpoint override. Animeka deep/mid tiers run
# on the RunPod L40S pod (Ollama, Qwen2.5 7B) because Vultr Serverless's
# Kimi/Qwen aliases return `content: null` for long-form Japanese prose.
# Format: {tier -> (endpoint_url, api_key_env, model_override_or_None)}.
# If the key env is unset OR empty, the override is silently ignored
# (caller falls back to the default Vultr endpoint + tier model).
_RUNPOD_LLM_URL = os.environ.get(
    "RUNPOD_LLM_URL",
    "https://vyp99t9px7h4dl-8000.proxy.runpod.net/v1/chat/completions",
)
_RUNPOD_LLM_MODEL = os.environ.get(
    "RUNPOD_LLM_MODEL", "qwen2.5:3b-instruct",
)

_OPENROUTER_LLM_URL = os.environ.get(
    "OPENROUTER_LLM_URL",
    "https://openrouter.ai/api/v1/chat/completions",
)
_OPENROUTER_LLM_MODEL = os.environ.get(
    "OPENROUTER_LLM_MODEL", "deepseek/deepseek-chat",
)

# Default resident LLM routing is now OpenRouter. `etzhayyim_LLM_URL` remains the generic
# env name consumed by existing graph code, but when it is unset we fall back
# to `OPENROUTER_LLM_URL` instead of the historical runpod/murakumo gateway.
_etzhayyim_LLM_URL = os.environ.get("etzhayyim_LLM_URL", "").strip() or _OPENROUTER_LLM_URL
_etzhayyim_LLM_MODEL = os.environ.get("etzhayyim_LLM_MODEL", "").strip() or _OPENROUTER_LLM_MODEL or None
_etzhayyim_KEY_ENV = "OPENROUTER_API_KEY"

TIER_ENDPOINT_OVERRIDES: dict[str, tuple[str, str | None, str | None]] = {
    "deep":           (_etzhayyim_LLM_URL, _etzhayyim_KEY_ENV, _etzhayyim_LLM_MODEL),
    "mid":            (_etzhayyim_LLM_URL, _etzhayyim_KEY_ENV, _etzhayyim_LLM_MODEL),
    "classifier":     (_etzhayyim_LLM_URL, _etzhayyim_KEY_ENV, _etzhayyim_LLM_MODEL),
    "structured":     (_etzhayyim_LLM_URL, _etzhayyim_KEY_ENV, _etzhayyim_LLM_MODEL),
    "fast":           (_etzhayyim_LLM_URL, _etzhayyim_KEY_ENV, _etzhayyim_LLM_MODEL),
    # SES extraction: always llm.etzhayyim.com; model resolved from TIER_MODELS["ses-extraction"].
    "ses-extraction": (_etzhayyim_LLM_URL, _etzhayyim_KEY_ENV, None),
}
# Empirical (2026-04-22): Vultr Serverless occasionally hangs for 30s+ then
# recovers within 5s on retry. Per-attempt timeout 20s + 1 retry keeps the
# worst case bounded to ~42s while still catching transient 5xx storms.
_DEFAULT_TIMEOUT_SEC = 20.0
_RETRY_BACKOFF_SEC = 2.0
_RETRY_MAX_ATTEMPTS = 2  # initial try + 1 retry

Tier = Literal["fast", "classifier", "structured", "reasoning", "frontier", "deep", "mid"]

TIER_MODELS: dict[str, str] = {
    "fast": "mistralai/Devstral-2-123B-Instruct-2512",
    "classifier": "mistralai/Devstral-2-123B-Instruct-2512",
    "structured": "mistralai/Devstral-2-123B-Instruct-2512",
    "reasoning": "Qwen/Qwen3.5-397B-A17B-FP8",
    "frontier": "moonshotai/Kimi-K2.6",
    # ADR-2604231328 animeka pipeline tiers. `deep` = creative long-form
    # (screenplay / storyboard prose / background description). `mid` =
    # balanced default for director-style tasks. Aliased onto existing
    # Vultr Serverless models; once the RunPod L40S text-gen endpoint is
    # live, `_endpoint_for_tier()` will route `deep` there instead.
    "deep": "moonshotai/Kimi-K2.6",
    "mid":  "Qwen/Qwen3.5-397B-A17B-FP8",
    # Generic alias used by newsletter/webmk LangGraph nodes.
    "default": "claude-sonnet-4-5",
    # SES案件 ingest extraction (ADR-2605120000). Routed via llm.etzhayyim.com →
    # OpenRouter → DeepSeek Pro V4. Model ID overridable via SES_EXTRACTOR_MODEL.
    "ses-extraction": os.environ.get("SES_EXTRACTOR_MODEL", "deepseek/deepseek-chat"),
}


class LlmError(RuntimeError):
    """Raised for transport / upstream errors. Handlers should catch and
    fold into their own JSON error envelope rather than bubbling up — UDF
    handlers must always return a VARCHAR."""


def resolve_model(tier_or_model: str) -> str:
    """Accept either a tier label or a raw model ID. Unknown tiers raise."""
    if "/" in tier_or_model:
        # Treat HF-style IDs as a direct model pin.
        return tier_or_model
    model = TIER_MODELS.get(tier_or_model)
    if not model:
        raise LlmError(f"unknown tier: {tier_or_model!r}")
    return model


# Alias used by newsletter_worker_main / webmk_worker_main ChatAnthropic nodes.
resolve_model_id = resolve_model


def _api_key() -> str:
    key = os.environ.get(_KEY_ENV, "").strip()
    if not key:
        raise LlmError(f"{_KEY_ENV} not set in pod env")
    return key


def call_tier(
    tier: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 400,
    temperature: float = 0.1,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Single-turn chat completion with a tier-picked model.

    Returns a dict with `content`, `reasoning`, `finish`, `usage`, `model`,
    `latencyMs`. Raises `LlmError` on transport failures — callers should
    catch and wrap for their UDF response envelope.

    `extra` merges into the upstream payload before POST (e.g. `top_p`,
    `stop`, `response_format` once Vultr supports it). Keys must use the
    OpenAI-compatible snake_case names.
    """
    # Per-tier endpoint + model override (RunPod text-gen). Falls back to
    # the default Vultr endpoint + tier model when no override applies.
    # RunPod cold-start on first inference can take 60-90s; bump the
    # per-attempt timeout for override tiers so we don't give up early.
    override = TIER_ENDPOINT_OVERRIDES.get(tier)
    if override:
        endpoint, key_env, model_override = override
        model = model_override or resolve_model(tier)
        if timeout_sec == _DEFAULT_TIMEOUT_SEC:
            # llm.etzhayyim.com → murakumo (warm fleet, no cold-start); 60s is generous.
            # Legacy RunPod cold-start required 120s; keep 60s for all gateways.
            timeout_sec = 60.0
    else:
        endpoint = _ENDPOINT
        key_env = _KEY_ENV
        model = resolve_model(tier)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    if extra:
        payload.update(extra)

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        # RunPod proxy (*.proxy.runpod.net) sits behind Cloudflare and
        # returns 1010 to python/urllib's default UA. A standard browser
        # UA keeps the request acceptable regardless of endpoint.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    if key_env:
        api_key = os.environ.get(key_env, "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    # Internal gateway credits gate: bypassed for trusted in-cluster callers.
    if "llm.etzhayyim.com" in endpoint or "murakumo.etzhayyim.com" in endpoint:
        headers["x-kotoba-kotodama-verified"] = "true"

    started = time.monotonic()
    raw: bytes | None = None
    last_err: Exception | None = None
    attempts = 0
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        attempts = attempt
        req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read()
            break
        except urllib.error.HTTPError as e:
            # 4xx errors are permanent (auth / bad request / model gone). Don't retry.
            if 400 <= e.code < 500:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:300]
                except Exception:
                    pass
                raise LlmError(f"upstream http {e.code}: {detail}") from e
            # 5xx: transient upstream, retry once.
            last_err = LlmError(f"upstream http {e.code}")
        except urllib.error.URLError as e:
            last_err = LlmError(f"upstream url error: {e.reason}")
        except TimeoutError as e:
            last_err = LlmError(f"upstream timeout after {timeout_sec}s")
        if attempt < _RETRY_MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_SEC)

    if raw is None:
        # All attempts exhausted.
        assert last_err is not None
        raise last_err

    latency_ms = int((time.monotonic() - started) * 1000)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LlmError(f"upstream returned non-JSON: {e}") from e

    choices = parsed.get("choices") or []
    first = choices[0] if choices else {}
    message = first.get("message") or {}

    return {
        "content": message.get("content"),
        "reasoning": message.get("reasoning") or message.get("reasoning_content"),
        "finish": first.get("finish_reason"),
        "usage": parsed.get("usage"),
        "model": parsed.get("model", model),
        "latencyMs": latency_ms,
        "attempts": attempts,
    }


def _strip_code_fence(text: str) -> str:
    """Handle ```json ... ``` wrapping that classifier-style models sometimes
    emit despite an explicit ban in the system prompt.

    Two shapes observed from Vultr Devstral in the wild:
      (a) Full fence:  ```json\n{...}\n```
      (b) Open-only:   ```\n{...}          (truncated / no closing fence)
    Handle both — the earlier splitlines()[1:-1] approach collapsed (b) to
    an empty string because there were only 2 lines.
    """
    text = text.strip()
    if not text.startswith("```"):
        return text
    newline = text.find("\n")
    if newline == -1:
        # Pathological ``` with no body — give up.
        return text
    text = text[newline + 1:].strip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    """Find the first balanced `{...}` block. Used as a last-resort parse
    when the model prepends prose before the JSON answer."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_json_content(content: str | None) -> dict[str, Any] | None:
    """
    Best-effort parse of a model's JSON answer. Returns None if no valid
    JSON object can be recovered.

    Order:
      1. Exact JSON
      2. After stripping Markdown code fences
      3. First balanced `{...}` block in the text
    """
    if not content:
        return None
    text = _strip_code_fence(content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _extract_first_json_object(text)


def call_tier_json(
    tier: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 400,
    temperature: float = 0.1,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience wrapper around `call_tier` that expects the model to return
    a single JSON object. Returns
      {"ok": True, "data": {...}, "latencyMs": ..., "model": ..., "usage": ...}
    on success, or
      {"ok": False, "error": "...", "rawContent": "...", ...}
    on parse / transport failure.

    Handlers can forward this dict (or a subset of it) as their UDF response.
    """
    try:
        resp = call_tier(
            tier, system, user,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_sec=timeout_sec,
            extra=extra,
        )
    except LlmError as e:
        return {"ok": False, "error": str(e)}

    parsed = parse_json_content(resp["content"])
    if not parsed:
        return {
            "ok": False,
            "error": "failed to parse JSON from content",
            "rawContent": (resp["content"] or "")[:500],
            "model": resp["model"],
            "latencyMs": resp["latencyMs"],
            "finish": resp["finish"],
            "usage": resp["usage"],
        }
    return {
        "ok": True,
        "data": parsed,
        "model": resp["model"],
        "latencyMs": resp["latencyMs"],
        "attempts": resp.get("attempts"),
        "usage": resp["usage"],
    }


# ---------------------------------------------------------------------------
# Vision (multimodal) — P10.1b of ADR-2605141200
# ---------------------------------------------------------------------------
#
# Most TIER_* tiers (Devstral / Qwen / Kimi) are text-only RunPod/Vultr
# endpoints. Vision-capable models live on OpenAI's API today
# (gpt-4o-mini / gpt-4o). Rather than overload `call_tier` with a hard
# branch, we expose a sibling `call_tier_vision_json` that builds the
# OpenAI-style multimodal `messages` content (`[{type:"text"}, {type:
# "image_url"}, ...]`) and posts against an OpenAI-compatible endpoint
# resolved from env (`OPENAI_*` for the default `vision` tier).
#
# Adding new vision tiers = adding to `_VISION_TIER_OVERRIDES`. No
# breaking change to existing text-tier consumers.

_OPENAI_VISION_DEFAULT_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")
_OPENAI_VISION_DEFAULT_KEY_ENV = "OPENAI_API_KEY"

_VISION_TIER_OVERRIDES: dict[str, tuple[str, str, str]] = {
    # tier → (endpoint, key_env, default_model)
    "vision": (
        _OPENAI_VISION_DEFAULT_URL,
        _OPENAI_VISION_DEFAULT_KEY_ENV,
        os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini"),
    ),
    "vision-mini": (
        _OPENAI_VISION_DEFAULT_URL,
        _OPENAI_VISION_DEFAULT_KEY_ENV,
        os.environ.get("OPENAI_VISION_MINI_MODEL", "gpt-4o-mini"),
    ),
    "vision-frontier": (
        _OPENAI_VISION_DEFAULT_URL,
        _OPENAI_VISION_DEFAULT_KEY_ENV,
        os.environ.get("OPENAI_VISION_FRONTIER_MODEL", "gpt-4o"),
    ),
}


def call_tier_vision_json(
    tier: str,
    system: str,
    user: str,
    images_b64: list[str],
    *,
    max_tokens: int = 600,
    temperature: float = 0.2,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    extra: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """OpenAI-style multimodal chat completion that returns a JSON object.

    `tier` must be present in `_VISION_TIER_OVERRIDES`; the default is
    `"vision"` (gpt-4o-mini) so callers without strong opinions pick the
    cheapest vision endpoint. Each entry in `images_b64` is the raw
    base64-encoded image payload (no `data:` prefix — the wrapper adds it).

    `model` overrides the tier's default model id (e.g. caller wants a
    specific gpt-4o variant); falls back to the tier-resolved model when
    None or empty.

    Returns the same `{ok, data | error, ...}` envelope as
    `call_tier_json` so downstream handlers can ignore the dispatch detail.
    """
    override = _VISION_TIER_OVERRIDES.get(tier)
    if override is None:
        return {
            "ok": False,
            "error": f"unknown vision tier: {tier!r}",
        }
    endpoint, key_env, tier_model = override
    model = (model or "").strip() or tier_model
    key = os.environ.get(key_env, "").strip()
    if not key:
        return {
            "ok": False,
            "error": f"{key_env} not set in pod env (vision tier {tier!r})",
        }

    if not isinstance(images_b64, list) or not images_b64:
        return {"ok": False, "error": "images_b64 must be a non-empty list of base64 strings"}

    user_content: list[dict[str, Any]] = [{"type": "text", "text": user}]
    for b64 in images_b64:
        if not isinstance(b64, str) or not b64.strip():
            continue
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )
    if len(user_content) == 1:
        return {"ok": False, "error": "no valid image payloads after filtering"}

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        # JSON-mode hint — OpenAI ignores when the model doesn't support it.
        "response_format": {"type": "json_object"},
    }
    if extra:
        payload.update(extra)

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    import urllib.request
    import urllib.error

    req = urllib.request.Request(
        f"{endpoint}/chat/completions", data=body, headers=headers, method="POST"
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            detail = ""
        return {
            "ok": False,
            "error": f"vision LLM {e.code}: {detail}",
            "latencyMs": int((time.monotonic() - started) * 1000),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"vision LLM transport: {e!s}",
            "latencyMs": int((time.monotonic() - started) * 1000),
        }

    latency_ms = int((time.monotonic() - started) * 1000)

    try:
        parsed_raw = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"vision LLM returned non-JSON: {e}"}

    choices = parsed_raw.get("choices") or []
    first = choices[0] if choices else {}
    message = first.get("message") or {}
    content = message.get("content")

    parsed = parse_json_content(content)
    if not parsed:
        return {
            "ok": False,
            "error": "failed to parse JSON from vision content",
            "rawContent": (content or "")[:500],
            "model": parsed_raw.get("model", model),
            "latencyMs": latency_ms,
        }
    return {
        "ok": True,
        "data": parsed,
        "model": parsed_raw.get("model", model),
        "latencyMs": latency_ms,
        "usage": parsed_raw.get("usage"),
        "imageCount": len(user_content) - 1,
    }


__all__ = [
    "Tier",
    "TIER_MODELS",
    "LlmError",
    "resolve_model",
    "resolve_model_id",
    "call_tier",
    "call_tier_json",
    "call_tier_vision_json",
    "parse_json_content",
]
