"""
ADR-0049 Phase B5 — mangaka storyboard-from-prompt UDF.

Takes a free-form story premise plus optional layout hints and returns
a structured storyboard (pages × panels × shot/description/dialogue/sfx)
via `kotodama.llm.call_tier_json`. Routes through Vultr Serverless
Devstral-2-123B — same tier as classify_t3 and news_translate.

Designed to drop into a SQL call site:

    SELECT mangaka_storyboard_from_prompt(
      '{"story": "a schoolgirl discovers a sentient library",
        "pageCount": 3, "panelsPerPage": 4, "style": "shonen"}'
    ) AS storyboard_json;

or chained from the mangaka Worker after a `projectChat` message lands.

The handler intentionally does NOT write to the graph. The storyboard
JSON lands back in the caller; the Worker is responsible for materializing
pages/panels into `vertex_mangaka` rows with correct `parent_rkey` /
`page_number` / `panel_number` (those wiring columns already exist in
the schema).

Failure policy:
  - Invalid input JSON      → {"error": "invalid JSON: ..."}
  - LLM transport failure   → {"error": "...", "attempts": N}
  - Malformed model output  → {"error": "failed to parse JSON",
                               "rawContent": "<=500 chars"}
  - Success                 → {"pages": [...], "model", "latencyMs",
                               "usage", "attempts"}
"""

from __future__ import annotations

import json
from typing import Any

from kotodama import udf
from kotodama import llm

_DEFAULT_PAGES = 3
_DEFAULT_PANELS_PER_PAGE = 4
_MAX_PAGES = 8
_MAX_PANELS_PER_PAGE = 6
_DEFAULT_STYLE = "shonen"
_VALID_STYLES = {"shonen", "seinen", "shojo", "josei", "kodomo"}
_DEFAULT_MAX_TOKENS = 1400  # 3×4 panels × ~100 tok per panel + overhead

_SYSTEM_PROMPT = """\
You are a professional manga storyboard artist. Given a one-line story \
premise plus optional layout/style hints, output ONE JSON object with \
exactly this shape (newlines added here for readability, but output \
minified with no preamble and no code fences):

  {
    "pages": [
      {
        "pageNumber": <int>,
        "panels": [
          {
            "panelNumber": <int>,
            "shot": "wide|medium|close-up|extreme-close-up|establishing|over-the-shoulder|pov|bird-eye",
            "description": "<=120 chars visual beat, no dialogue",
            "dialogue": "<=80 chars, or empty string",
            "sfx": "<=20 chars, or empty string"
          }
        ]
      }
    ]
  }

Match pageCount × panelsPerPage exactly.
Output ONLY the JSON object — no preamble, no commentary, no code fences."""


def _err(msg: str, **extra: Any) -> str:
    return json.dumps({"error": msg, **extra})


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


@udf(
    nsid="com.etzhayyim.apps.mangaka.storyboardFromPrompt",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("mangaka", "storyboard", "llm", "generation"),
    agent_tool="Generate a structured manga storyboard (pages × panels) from a one-line premise.",
)
def storyboard_from_prompt(request_json: str) -> str:
    """
    Input JSON:
      {"story": str (required, one-line premise),
       "pageCount": int (optional, default 3, max 8),
       "panelsPerPage": int (optional, default 4, max 6),
       "style": str (optional, one of shonen|seinen|shojo|josei|kodomo,
                     default shonen),
       "tier": str (optional, llm tier; default "classifier"),
       "maxTokens": int (optional; default 1400)}

    Output JSON:
      success → {"pages": [...], "style", "model", "latencyMs", "usage", "attempts"}
      error   → {"error": str, ...}
    """

    try:
        body = json.loads(request_json) if request_json else {}
    except json.JSONDecodeError as e:
        return _err(f"invalid JSON: {e}")
    if not isinstance(body, dict):
        return _err("request must be a JSON object")
    # XRPC body wrapper tolerance.
    if "json" in body and isinstance(body.get("json"), dict):
        body = body["json"]

    story = str(body.get("story") or "").strip()
    if not story:
        return _err("story is required")

    page_count = _clamp_int(body.get("pageCount"), _DEFAULT_PAGES, 1, _MAX_PAGES)
    panels_per_page = _clamp_int(
        body.get("panelsPerPage"), _DEFAULT_PANELS_PER_PAGE, 1, _MAX_PANELS_PER_PAGE,
    )
    style = str(body.get("style") or _DEFAULT_STYLE).lower()
    if style not in _VALID_STYLES:
        style = _DEFAULT_STYLE
    tier = str(body.get("tier") or "classifier")
    try:
        max_tokens = int(body.get("maxTokens") or _DEFAULT_MAX_TOKENS)
    except (TypeError, ValueError):
        max_tokens = _DEFAULT_MAX_TOKENS

    user_prompt = (
        f"Story premise: {story}\n"
        f"Style: {style}\n"
        f"pageCount: {page_count}\n"
        f"panelsPerPage: {panels_per_page}\n"
        f"Total panels to emit: {page_count * panels_per_page}\n"
        "Draft the storyboard now."
    )

    result = llm.call_tier_json(
        tier,
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=max_tokens,
        temperature=0.4,
    )

    if not result.get("ok"):
        return json.dumps(result)

    data = result["data"]
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        return json.dumps(
            {
                "error": "LLM returned no pages array",
                "rawData": str(data)[:500],
                "model": result["model"],
                "latencyMs": result["latencyMs"],
                "attempts": result.get("attempts"),
            }
        )

    return json.dumps(
        {
            "pages": pages,
            "style": style,
            "pageCount": page_count,
            "panelsPerPage": panels_per_page,
            "model": result["model"],
            "usage": result["usage"],
            "latencyMs": result["latencyMs"],
            "attempts": result.get("attempts"),
        }
    )
