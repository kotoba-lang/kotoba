"""
ADR-0050 — Vultr Serverless Inference UDF.

Streams inference from `api.vultrinference.com/v1/chat/completions` as a
RisingWave SQL function. Call site examples:

  SELECT vultr_chat_completions(
    '{"model":"Qwen/Qwen3.5-397B-A17B-FP8",
      "messages":[{"role":"user","content":"say hi"}],
      "maxTokens":200}'
  );

  -- Streaming MV: summarize every inbound email.
  CREATE MATERIALIZED VIEW email_summary AS
  SELECT
    id,
    vultr_chat_completions(
      json_build_object(
        'model','Qwen/Qwen3.5-397B-A17B-FP8',
        'messages', json_build_array(
          json_build_object('role','system','content','Summarize in one sentence.'),
          json_build_object('role','user','content', body)
        ),
        'maxTokens', 64
      )::varchar
    ) AS summary
  FROM stream_inbox;

Authentication comes from the `VULTR_SERVERLESS_KEY` env var injected into
the mitama-udf pod via K8s Secret `vultr-serverless` (helm template +
`envFrom.secretRef`).

Inference stays entirely within Vultr: mitama-udf pod (VKE LAX) →
api.vultrinference.com (same provider, Bandwidth Alliance internal). No CF
Worker hop, no external egress fee.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from kotodama import udf

_ENDPOINT = "https://api.vultrinference.com/v1/chat/completions"
_DEFAULT_TIMEOUT_SEC = 35.0
_KEY_ENV = "VULTR_SERVERLESS_KEY"


def _err(msg: str, **extra: Any) -> str:
    return json.dumps({"error": msg, **extra})


@udf(
    nsid="com.etzhayyim.apps.vultrInference.chatCompletions",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("inference", "llm", "vultr-serverless"),
    agent_tool="Vultr Serverless Inference chat/completions (OpenAI-compatible).",
)
def chat_completions(request_json: str) -> str:
    """
    Input:  JSON `{model, messages[], maxTokens?, temperature?, topP?, stop?}`
    Output: JSON `{content, finishReason, usage, latencyMs, model}` or
            `{error, ...}`.

    `max_tokens` / `max_completion_tokens` accept camelCase and snake_case
    synonyms — handlers reached from both Kysely-typed TS callers and raw
    SQL differ on casing.
    """

    api_key = os.environ.get(_KEY_ENV, "").strip()
    if not api_key:
        return _err(f"{_KEY_ENV} not set in pod env")

    try:
        body = json.loads(request_json) if request_json else {}
    except json.JSONDecodeError as e:
        return _err(f"invalid JSON: {e}")

    if not isinstance(body, dict):
        return _err("request must be a JSON object")

    # XRPC body wrapper tolerance (matches bpmn.py pattern).
    if "json" in body and isinstance(body.get("json"), dict):
        body = body["json"]

    model = body.get("model")
    messages = body.get("messages")
    if not isinstance(model, str) or not model:
        return _err("'model' is required (e.g. Qwen/Qwen3.5-397B-A17B-FP8)")
    if not isinstance(messages, list) or not messages:
        return _err("'messages' must be a non-empty array")

    # Assemble OpenAI-compatible upstream payload. Pass through all standard
    # knobs, preferring the camelCase alias where both are present.
    upstream: dict[str, Any] = {"model": model, "messages": messages}
    max_tokens = body.get("maxTokens", body.get("max_tokens"))
    if isinstance(max_tokens, (int, float)):
        upstream["max_tokens"] = int(max_tokens)
    for key_cc, key_sc in (
        ("temperature", "temperature"),
        ("topP", "top_p"),
        ("frequencyPenalty", "frequency_penalty"),
        ("presencePenalty", "presence_penalty"),
        ("stop", "stop"),
    ):
        v = body.get(key_cc, body.get(key_sc))
        if v is not None:
            upstream[key_sc] = v

    payload = json.dumps(upstream).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT_SEC) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        return _err(f"upstream http {e.code}", detail=detail)
    except urllib.error.URLError as e:
        return _err(f"upstream url error: {e.reason}")
    except TimeoutError:
        return _err(f"upstream timeout after {_DEFAULT_TIMEOUT_SEC}s")
    except Exception as e:  # noqa: BLE001 — surface any transport surprise
        return _err(f"upstream transport error: {e}")

    latency_ms = int((time.monotonic() - started) * 1000)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return _err(f"upstream returned non-JSON: {e}", rawHead=raw[:200].decode("utf-8", errors="replace"))

    if status != 200:
        return _err(f"upstream http {status}", upstream=parsed)

    choices = parsed.get("choices") or []
    first = choices[0] if choices else {}
    message = first.get("message") or {}
    content = message.get("content")
    reasoning = message.get("reasoning_content")

    return json.dumps(
        {
            "content": content,
            "reasoningContent": reasoning,
            "finishReason": first.get("finish_reason"),
            "usage": parsed.get("usage"),
            "model": parsed.get("model", model),
            "latencyMs": latency_ms,
        }
    )
