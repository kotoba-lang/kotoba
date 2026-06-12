"""
ADR-0032 / ADR-0050 — T3 gray-zone phishing classifier.

Sits on top of `classify_t1` SQL UDF. When T1 scores the mail in the
gray zone (60 <= t1 < 85) the stream invokes this UDF; it prompts a
Vultr Serverless Inference model (via `kotodama.llm` tier abstraction)
to give a second opinion + natural language rationale.

Rows outside the gray zone short-circuit without an HTTP call — the
caller gets `{skipped: true}` back so downstream logic can keep the
T1 decision unchanged. This keeps frontier-model cost bounded to
~10-20% of inbound mail by volume.

Inference path: mitama-udf pod → api.vultrinference.com/v1/chat/completions
(same Vultr provider, Bandwidth Alliance internal). No CF Worker hop.
"""

from __future__ import annotations

import json
from typing import Any

from kotodama import udf
from kotodama import llm

_GRAY_LOW = 60
_GRAY_HIGH = 85
_DEFAULT_TIER = "classifier"
_DEFAULT_MAX_TOKENS = 200

_SYSTEM_PROMPT = (
    "You are a phishing triage assistant. You receive email metadata and a "
    "T1 heuristic score (0-100) and must output ONE JSON object with keys "
    "score (0-100 integer, your independent estimate), verdict "
    "(one of: phishing, legitimate, ambiguous), rationale (<=200 chars, "
    "plain text, no markdown). Output ONLY the JSON object, no preamble, "
    "no trailing commentary. Do not wrap in code fences."
)


def _err(msg: str, **extra: Any) -> str:
    return json.dumps({"error": msg, **extra})


def _skip(reason: str, **extra: Any) -> str:
    return json.dumps({"skipped": True, "reason": reason, **extra})


def _build_user_prompt(fields: dict[str, Any]) -> str:
    """Compact single-block user prompt. Order chosen to front-load signal."""
    parts = [
        f"T1 score: {fields.get('t1Score')}",
        f"From: {fields.get('fromAddr', '')}",
        f"Subject: {fields.get('subject', '')}",
        f"Reply-To: {fields.get('replyTo', '')}",
        f"SPF: {fields.get('spf', '')} / DKIM: {fields.get('dkim', '')} / DMARC: {fields.get('dmarc', '')}",
    ]
    body_urls = fields.get("bodyUrls") or []
    if isinstance(body_urls, list) and body_urls:
        shown = [str(u) for u in body_urls[:5]]
        parts.append(f"Body URLs: {', '.join(shown)}")
    return "\n".join(parts)


@udf(
    nsid="com.etzhayyim.apps.yabaiClassifier.phishingT3",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("yabai", "phishing", "t3", "gray-zone"),
    agent_tool="Phishing T3 gray-zone classifier — LLM second opinion on T1 60-84 scores.",
)
def phishing_t3(request_json: str) -> str:
    """
    Input: JSON
      {"t1Score": int, "fromAddr": str, "subject": str, "replyTo": str,
       "spf": str, "dkim": str, "dmarc": str, "bodyUrls": [str],
       "tier": str (optional; default "classifier"),
       "maxTokens": int (optional; default 200)}

    Output: JSON — one of
      {"skipped": true, "reason": "not-gray-zone", "t1Score": ...}
      {"t1Score": int, "llmScore": int, "verdict": "phishing|legitimate|ambiguous",
       "rationale": str, "model": str, "latencyMs": int, "usage": {...}}
      {"error": str, ...}
    """

    try:
        fields = json.loads(request_json) if request_json else {}
    except json.JSONDecodeError as e:
        return _err(f"invalid JSON: {e}")
    if not isinstance(fields, dict):
        return _err("request must be a JSON object")

    # XRPC body wrapper tolerance.
    if "json" in fields and isinstance(fields.get("json"), dict):
        fields = fields["json"]

    raw_t1 = fields.get("t1Score", fields.get("t1_score"))
    try:
        t1_score = int(raw_t1) if raw_t1 is not None else None
    except (TypeError, ValueError):
        return _err("t1Score must be an integer 0-100")
    if t1_score is None:
        return _err("t1Score is required")

    # Short-circuit outside the gray zone. The stream keeps the T1 decision.
    if t1_score < _GRAY_LOW or t1_score >= _GRAY_HIGH:
        return _skip("not-gray-zone", t1Score=t1_score)

    tier = str(fields.get("tier") or _DEFAULT_TIER)
    try:
        max_tokens = int(fields.get("maxTokens") or _DEFAULT_MAX_TOKENS)
    except (TypeError, ValueError):
        max_tokens = _DEFAULT_MAX_TOKENS

    result = llm.call_tier_json(
        tier,
        system=_SYSTEM_PROMPT,
        user=_build_user_prompt(fields),
        max_tokens=max_tokens,
        temperature=0.1,
    )

    if not result.get("ok"):
        # Preserve failure metadata so callers can distinguish transport
        # errors from parse failures.
        return json.dumps({"t1Score": t1_score, **result})

    data = result["data"]
    llm_score = data.get("score")
    try:
        llm_score = int(llm_score) if llm_score is not None else None
    except (TypeError, ValueError):
        llm_score = None

    verdict_label = str(data.get("verdict") or "").lower()
    if verdict_label not in ("phishing", "legitimate", "ambiguous"):
        verdict_label = "ambiguous"

    return json.dumps(
        {
            "t1Score": t1_score,
            "llmScore": llm_score,
            "verdict": verdict_label,
            "rationale": str(data.get("rationale") or "")[:300],
            "model": result["model"],
            "usage": result["usage"],
            "latencyMs": result["latencyMs"],
        }
    )
