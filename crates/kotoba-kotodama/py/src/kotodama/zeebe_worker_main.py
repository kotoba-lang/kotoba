"""
ADR-0049 Pattern 5 / Z3 — in-cluster Zeebe worker entrypoint.

Subscribes to the four `com.etzhayyim.devstral.*` job types that map 1:1 to the
existing UDF handlers, but calls `kotodama.llm` directly instead of
round-tripping through the SQL UDF layer. The SQL UDF surface remains
for streaming-MV / row-level use cases; this worker is for BPMN-driven
process orchestration.

Job type table (kept stable so BPMN definitions don't have to know
which engine implements them):

  com.etzhayyim.devstral.chat        → llm.call_tier (free-form chat)
  com.etzhayyim.devstral.classifyT3  → classify_t3 phishing JSON
  com.etzhayyim.devstral.translate   → news_translate semantics
  com.etzhayyim.devstral.storyboard  → mangaka_storyboard_from_prompt semantics

Run inside the cluster:
    python -m kotodama.zeebe_worker_main

Env:
  AGENTGATEWAY_MCP_URL      — gateway address (default agentgateway-mcp.mitama-udf.svc.cluster.local:8080)
  LANGSERVER_TIMEOUT_SEC  — per-job activation timeout (default 600)
  VULTR_SERVERLESS_KEY — required by kotodama.llm
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import signal
import time
from typing import Any

import urllib.request
from pathlib import Path

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

from kotodama import llm
# shinka node functions are imported lazily inside each task wrapper to
# avoid pulling LangGraph at module load when only Devstral tasks fire.

LOG = logging.getLogger("zeebe_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

GATEWAY = os.environ.get("AGENTGATEWAY_MCP_URL", "agentgateway-mcp.mitama-udf.svc.cluster.local:8080")
ACTIVATION_TIMEOUT = int(os.environ.get("LANGSERVER_TIMEOUT_SEC", "600"))

# ─── Helpers ─────────────────────────────────────────────────────────────

def _parse_verdict(content: str | None) -> dict[str, Any] | None:
    """Mirror of llm.parse_json_content for safety; tolerates stray prose
    around the JSON object."""
    return llm.parse_json_content(content)


# ─── Task implementations ────────────────────────────────────────────────

async def task_chat(prompt: str = "", system: str = "", tier: str = "fast",
                    max_tokens: int = 400, temperature: float = 0.3) -> dict:
    """Free-form chat. BPMN process passes prompt + optional system /
    tier knobs as variables; output stays under `content`/`model`/etc."""
    if not prompt:
        return {"error": "prompt is required"}
    try:
        resp = llm.call_tier(tier, system=system or "You are concise.",
                             user=prompt,
                             max_tokens=max_tokens, temperature=temperature)
    except llm.LlmError as e:
        return {"error": str(e)}
    return {
        "content": resp["content"],
        "reasoning": resp["reasoning"],
        "finish": resp["finish"],
        "model": resp["model"],
        "latencyMs": resp["latencyMs"],
        "attempts": resp["attempts"],
        "usage": resp["usage"],
    }


_PHISH_SYSTEM = (
    "You are a phishing triage assistant. You receive email metadata and "
    "a T1 heuristic score (0-100) and must output ONE JSON object with "
    "keys score (0-100 integer), verdict (phishing|legitimate|ambiguous), "
    "rationale (<=200 chars). Output ONLY the JSON object, no preamble, "
    "no code fences."
)


async def task_classify_t3(t1Score: int = 0, fromAddr: str = "",
                           subject: str = "", replyTo: str = "",
                           spf: str = "", dkim: str = "", dmarc: str = "",
                           bodyUrls: Any = None) -> dict:
    """Phishing T3 second-opinion. BPMN typically calls this after a T1
    SQL gate puts a row in the gray zone (60..84)."""
    if not isinstance(t1Score, int):
        try:
            t1Score = int(t1Score)
        except (TypeError, ValueError):
            return {"error": "t1Score must be int"}
    if t1Score < 60 or t1Score >= 85:
        return {"skipped": True, "reason": "not-gray-zone", "t1Score": t1Score}

    urls = bodyUrls if isinstance(bodyUrls, list) else []
    user = (
        f"T1 score: {t1Score}\nFrom: {fromAddr}\nSubject: {subject}\n"
        f"Reply-To: {replyTo}\nSPF: {spf} / DKIM: {dkim} / DMARC: {dmarc}\n"
        f"Body URLs: {', '.join(str(u) for u in urls[:5])}"
    )
    result = llm.call_tier_json("classifier", system=_PHISH_SYSTEM, user=user,
                                max_tokens=200, temperature=0.1)
    if not result.get("ok"):
        return {"t1Score": t1Score, **result}
    data = result["data"]
    verdict = str(data.get("verdict") or "").lower()
    if verdict not in ("phishing", "legitimate", "ambiguous"):
        verdict = "ambiguous"
    return {
        "t1Score": t1Score,
        "llmScore": data.get("score"),
        "verdict": verdict,
        "rationale": str(data.get("rationale") or "")[:300],
        "model": result["model"],
        "latencyMs": result["latencyMs"],
        "attempts": result["attempts"],
    }


_TRANSLATE_SYSTEM = (
    "You are a professional translator. Translate the user's text from "
    "the source language to the target language. Preserve named entities, "
    "URLs, and numeric values verbatim. Output ONLY the translated text. "
    "No preamble, no explanations, no quotation marks, no code fences."
)


async def task_translate(text: str = "", sourceLang: str = "auto",
                         targetLang: str = "ja") -> dict:
    """Single-string translation. Idempotent on same source/target."""
    if not text:
        return {"translated": ""}
    src = (sourceLang or "auto").strip() or "auto"
    dst = (targetLang or "").strip()
    if not dst or src == dst:
        return {"translated": text, "skipped": True, "reason": "same-language"}

    truncated = text if len(text) <= 800 else text[:800] + "…"
    user = f"Source language: {src}\nTarget language: {dst}\nText:\n{truncated}"
    try:
        resp = llm.call_tier("fast", system=_TRANSLATE_SYSTEM, user=user,
                             max_tokens=250, temperature=0.0)
    except llm.LlmError as e:
        # Match the SQL UDF graceful-degrade: return original text so the
        # downstream BPMN flow keeps moving.
        return {"translated": text, "error": str(e)}
    out = (resp.get("content") or "").strip()
    if (out.startswith('"') and out.endswith('"')) or (
        out.startswith("「") and out.endswith("」")
    ):
        out = out[1:-1].strip() or text
    return {
        "translated": out or text,
        "model": resp["model"],
        "latencyMs": resp["latencyMs"],
        "attempts": resp["attempts"],
    }


_STORYBOARD_SYSTEM = """\
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


async def task_storyboard(story: str = "", pageCount: int = 3,
                          panelsPerPage: int = 4, style: str = "shonen") -> dict:
    """Generate a multi-page manga storyboard. Mirrors the
    `mangaka_storyboard_from_prompt` UDF semantics."""
    if not story:
        return {"error": "story is required"}
    pageCount = max(1, min(int(pageCount or 3), 8))
    panelsPerPage = max(1, min(int(panelsPerPage or 4), 6))
    user = (
        f"Story premise: {story}\nStyle: {style}\n"
        f"pageCount: {pageCount}\npanelsPerPage: {panelsPerPage}\n"
        f"Total panels to emit: {pageCount * panelsPerPage}\n"
        "Draft the storyboard now."
    )
    result = llm.call_tier_json("classifier", system=_STORYBOARD_SYSTEM,
                                user=user, max_tokens=1400, temperature=0.4)
    if not result.get("ok"):
        return result
    data = result["data"]
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        return {"error": "no pages array", "model": result["model"],
                "latencyMs": result["latencyMs"]}
    return {
        "pages": pages,
        "style": style,
        "pageCount": pageCount,
        "panelsPerPage": panelsPerPage,
        "model": result["model"],
        "usage": result["usage"],
        "latencyMs": result["latencyMs"],
        "attempts": result["attempts"],
    }


async def task_llm_knowledge_retrieve(
    question: str = "",
    domain: str = "",
    gameSlug: str = "",
    lang: str = "ja",
    topK: int = 8,
) -> dict:
    """Retrieve domain knowledge from RisingWave for answerWithKnowledge."""
    if not question:
        return {"contexts": [], "citations": [], "usedKnowledge": [], "error": "question is required"}
    from kotodama.primitives import llm_knowledge

    return llm_knowledge.retrieve(
        question=question,
        domain=domain,
        gameSlug=gameSlug,
        lang=lang,
        topK=topK,
    )


async def task_llm_knowledge_langgraph_answer(
    question: str = "",
    contexts: list[dict[str, Any]] | None = None,
    citations: list[str] | None = None,
    tier: str = "fast",
    lang: str = "ja",
    model: str = "",
) -> dict:
    """Run the LangGraph evidence-to-answer node for answerWithKnowledge."""
    if not question:
        return {"answer": "", "confidence": "low", "model": model, "latencyMs": 0, "error": "question is required"}
    from kotodama.primitives import llm_knowledge

    return llm_knowledge.answer(
        question=question,
        contexts=contexts or [],
        citations=citations or [],
        tier=model or tier,
        lang=lang,
    )


# ─── kotoba-kotodama.shinka.* tasks (Phase Z-α, BPMN heartbeat migration) ──────
#
# Each task wraps one node from kotodama.shinka.__init__ (the existing
# LangGraph implementation). The BPMN process variables are mapped 1:1
# to the StateGraph state dict keys, just renamed to camelCase to match
# Zeebe convention (`actorDid`, `lastHeartbeatMs`, `followerDeltaCount`).
#
# We deliberately DON'T re-implement the node logic here — calling into
# kotodama.shinka guarantees the BPMN run produces bit-identical writes
# to vertex_actor_shinka_state / vertex_shinka_evolution as the legacy
# CronJob path. The two run side-by-side until A/B verification passes,
# then the CronJob is retired.


def _now_ms() -> int:
    return int(time.time() * 1000)


async def task_shinka_load_and_resolve(actorDid: str = "") -> dict:
    """Calls kotodama.shinka._load_state + _resolve_cadence in one shot.
    Returns the merged state so the XOR gateway can branch on `shouldPost`."""
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _load_state, _resolve_cadence
    state: dict[str, Any] = {"actor_did": actorDid, "now_ms": _now_ms()}
    state = _load_state(state)  # type: ignore[arg-type]
    state = _resolve_cadence(state)  # type: ignore[arg-type]
    # Re-export under camelCase Zeebe-friendly variable names. mood/axes
    # are passed through as-is (already simple JSON values).
    return {
        "mood": state.get("mood"),
        "axes": state.get("axes"),
        "lastHeartbeatMs": state.get("last_heartbeat_ms"),
        "shouldPost": bool(state.get("should_post")),
        "shouldEngage": bool(state.get("should_engage")),
        "shouldDrill": bool(state.get("should_drill")),
        "shouldValidate": bool(state.get("should_validate")),
        "shouldAnalyze": bool(state.get("should_analyze")),
        "actions": state.get("actions", []),
        "followerDeltaCount": state.get("follower_delta_count", 0),
        "tickMs": state["now_ms"],
    }


async def task_shinka_compose(actorDid: str = "", mood: str = "neutral",
                              axes: dict | None = None,
                              actions: list | None = None,
                              followerDeltaCount: int = 0) -> dict:
    """Mirror of kotodama.shinka._compose_content but driven by Zeebe
    inputs. Returns `draft` on success or `draft.error` on llm failure;
    either way the BPMN flow keeps moving (graceful degrade)."""
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _compose_content
    state = {
        "actor_did": actorDid,
        "now_ms": _now_ms(),
        "mood": mood,
        "axes": axes or {},
        "actions": actions or [],
        "follower_delta_count": int(followerDeltaCount or 0),
        "should_post": True,  # gateway already filtered
    }
    state = _compose_content(state)  # type: ignore[arg-type]
    return {
        "draft": state.get("compose_draft"),
        "actions": state.get("actions", actions or []),
    }


async def task_shinka_write_heartbeat(actorDid: str = "", mood: str = "neutral",
                                      actions: list | None = None) -> dict:
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _write_heartbeat
    state = {
        "actor_did": actorDid,
        "now_ms": _now_ms(),
        "mood": mood,
        "actions": actions or [],
    }
    state = _write_heartbeat(state)  # type: ignore[arg-type]
    return {"heartbeatWritten": bool(state.get("heartbeat_written")),
            "tickMs": state["now_ms"]}


async def task_shinka_emit_evolution(actorDid: str = "", mood: str = "neutral",
                                     axes: dict | None = None,
                                     actions: list | None = None,
                                     followerDeltaCount: int = 0,
                                     draft: dict | None = None) -> dict:
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _emit_evolution
    state = {
        "actor_did": actorDid,
        "now_ms": _now_ms(),
        "mood": mood,
        "axes": axes or {},
        "actions": actions or [],
        "follower_delta_count": int(followerDeltaCount or 0),
        "compose_draft": draft,
    }
    state = _emit_evolution(state)  # type: ignore[arg-type]
    return {"evolutionWritten": bool(state.get("evolution_written")),
            "tickMs": state["now_ms"]}


# ─── F1: generic.* primitives (BPMN-as-actor architecture) ───────────────
#
# These four task types let a BPMN process express most actor behavior
# without any actor-specific Python. Combined with BPMN gateways/timers,
# ~80% of T1/T2 actors should be expressible as pure data (BPMN XML +
# lexicon binding, no per-actor code).
#
# Security model:
#   - SQL is composed by the BPMN author (a deployment artifact, not
#     end-user input). We allow-list table names that match
#     `vertex_*` / `edge_*` / `mv_*` to keep accidental damage bounded.
#   - Where clauses use parameterized psycopg ($1, $2, ...) — no raw
#     interpolation of user values.
#   - generic.llm.* uses the same kotodama.llm path that already
#     powers classify_t3 / news_translate / mangaka_storyboard, so no
#     new auth surface.


_ALLOWED_TABLE_RE = re.compile(r"^(vertex|edge|mv)_[a-z0-9_]+$")


def _check_table(name: str) -> None:
    if not _ALLOWED_TABLE_RE.match(name):
        raise ValueError(f"table name not allow-listed: {name!r}")


# Per-binding write_table_allowlist enforcement (2026-04-25, defence cluster).
# LangServer holds root psycopg credentials; without per-actor scoping any
# well-formed BPMN can target any vertex_*/edge_* table. Wave 1-5 defence
# stubs all write to `vertex_open_defence_event` only — we look up the
# binding's `write_table_allowlist` (CSV column on
# vertex_bpmn_lexicon_binding) by bpmn_process_id and reject when the
# task's `table` argument isn't a member.
#
# NULL allowlist = legacy / unrestricted (preserves backwards compat for
# bindings created before mig 20260425160000). Empty string = explicit
# "deny all writes" (use to lock a binding down to read-only tasks).
def _binding_write_allowlist(bpmn_process_id: str) -> set[str] | None:
    if not bpmn_process_id:
        return None
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT write_table_allowlist FROM vertex_bpmn_lexicon_binding "
                "WHERE bpmn_process_id = %s LIMIT 1",
                (bpmn_process_id,),
            )
            row = (_res[0] if _res else None)
    except Exception:  # noqa: BLE001  — table may not have the column yet
        return None
    if not row or row[0] is None:
        return None
    csv = (row[0] or "").strip()
    if not csv:
        return set()  # explicit deny
    return {t.strip() for t in csv.split(",") if t.strip()}


def _enforce_write_scope(table: str, bpmn_process_id: str) -> str | None:
    """Return an error string if `table` is outside the binding allowlist."""
    allow = _binding_write_allowlist(bpmn_process_id)
    if allow is None:
        return None  # legacy / no binding = unrestricted
    if not allow:
        return f"binding {bpmn_process_id} has empty write_table_allowlist (write denied)"
    if table not in allow:
        return (
            f"table {table!r} not in write_table_allowlist for "
            f"bpmn_process_id={bpmn_process_id!r} (allowed: {sorted(allow)})"
        )
    return None


# Column name grammar for extraFilters. Matches lowercase SQL conventions:
# letter/underscore start, then alnum/underscore. RW columns are all
# snake_case so this covers the safe subset. Anything else gets rejected
# before it reaches the SQL text.
_COLUMN_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

# Operators we'll splice into WHERE via extraFilters. Each one is a
# single-token comparison with one `%s` bind parameter. LIKE is allowed
# for prefix/suffix search; IN is NOT allowed here (would need array
# binding and a different shape — add when there's a real caller).
_ALLOWED_FILTER_OPS = {"=", "!=", "<>", "<", ">", "<=", ">=", "LIKE", "ILIKE"}

# `columns` validator. We accept any of:
#   *
#   DISTINCT col
#   col[, col[...]]
#   col AS alias[, ...]           (alias is snake_case column name)
# — but reject parens, semicolons, quotes, comments. This covers every
# BPMN call-site audited 2026-04-23 (`*`, `DISTINCT repo_did`, comma
# lists, a few `col AS alias`) without opening the door to a full
# expression parser. Anything more exotic must use a typed primitive.
_COLUMN_EXPR_RE = re.compile(
    r"^\s*(?:DISTINCT\s+)?"
    r"(?:[a-z_][a-z0-9_]*(?:\s+AS\s+[a-z_][a-z0-9_]*)?)"
    r"(?:\s*,\s*[a-z_][a-z0-9_]*(?:\s+AS\s+[a-z_][a-z0-9_]*)?)*"
    r"\s*$",
    re.IGNORECASE,
)

# `orderBy` validator. Accepts `col [ASC|DESC][, col [ASC|DESC]]*`.
_ORDER_BY_RE = re.compile(
    r"^\s*[a-z_][a-z0-9_]*(?:\s+(?:ASC|DESC))?"
    r"(?:\s*,\s*[a-z_][a-z0-9_]*(?:\s+(?:ASC|DESC))?)*\s*$",
    re.IGNORECASE,
)


def _check_columns(cols: str) -> None:
    if cols.strip() == "*":
        return
    if not _COLUMN_EXPR_RE.match(cols):
        raise ValueError(f"columns not allow-listed: {cols!r}")


def _check_order_by(order_by: str) -> None:
    if not _ORDER_BY_RE.match(order_by):
        raise ValueError(f"orderBy not allow-listed: {order_by!r}")


async def task_generic_db_select(sql: str = "", params: list | None = None,
                                 query: str = "",
                                 table: str = "", whereExpr: str = "",
                                 whereParams: list | None = None,
                                 columns: str = "*",
                                 limit: int = 50,
                                 orderBy: str = "",
                                 extraFilters: list | None = None) -> dict:
    """SELECT primitive.

    Raw SQL path (BPMN-as-actor): `sql` is a full parameterized SELECT
    statement using PostgreSQL $1/$2/... placeholders; `params` is the
    ordered list of bind values. The $N placeholders are converted to %s
    for psycopg before execution. No table allow-list check is applied in
    this path (the SQL is authored in BPMN XML, not derived from user input).
    `query` is accepted as a backwards-compatible alias used by older BPMN
    contracts.

    Legacy path: `whereExpr` is a parameterized SQL fragment with
    `whereParams` as the matching ordered list.

    Dynamic path (added 2026-04-23): `extraFilters` is a list of
    `{column, op?, value}` dicts.

    Returns up to limit rows as list-of-dicts under key `rows`."""
    import re as _re

    if query and not sql:
        sql = query

    # Raw SQL path: full SELECT statement with $N placeholders.
    if sql:
        # RisingWave rejects LIMIT/OFFSET $N in prepared statements.
        # Pre-inline LIMIT/OFFSET $N before the general %s substitution.
        _param_list = list(params or [])
        def _inline_limit(m: "_re.Match[str]") -> str:
            idx = int(m.group(2)) - 1
            return f"{m.group(1)}{int(_param_list[idx])}"
        sql = _re.sub(r"\b(LIMIT\s+|OFFSET\s+)\$(\d+)\b", _inline_limit, sql, flags=_re.IGNORECASE)
        # Convert $1, $2, ... to %s for psycopg, expanding repeated references.
        # e.g. "... <=> $1::vector ... <=> $1::vector ..." with params=[vec]
        # produces bind=[vec, vec] matching two %s placeholders.
        _indices = [int(m.group(1)) for m in _re.finditer(r"\$(\d+)", sql)]
        psycopg_sql = _re.sub(r"\$\d+", "%s", sql)
        bind = [_param_list[i - 1] for i in _indices]
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(psycopg_sql, tuple(bind))
                col_names = [d[0] for d in []] if [] else []
                raw = _res or []
            import datetime
            from decimal import Decimal
            def _coerce(v: Any) -> Any:
                if isinstance(v, (datetime.date, datetime.datetime)):
                    return v.isoformat()
                if isinstance(v, Decimal):
                    return float(v)
                if isinstance(v, (bytes, bytearray)):
                    try:
                        return v.decode("utf-8")
                    except UnicodeDecodeError:
                        import base64
                        return base64.b64encode(v).decode("ascii")
                return v
            rows = [{k: _coerce(v) for k, v in dict(zip(col_names, r)).items()}
                    for r in raw]
            return {"rows": rows, "rowCount": len(rows)}
        except Exception as e:  # noqa: BLE001
            return {"error": f"db.select failed: {e}", "rows": [], "rowCount": 0}

    if not table:
        return {"error": "table required"}
    _check_table(table)
    cols_raw = columns or "*"
    try:
        _check_columns(cols_raw)
    except ValueError as e:
        return {"error": f"db.select: {e}", "rows": [], "rowCount": 0}
    if orderBy:
        try:
            _check_order_by(orderBy)
        except ValueError as e:
            return {"error": f"db.select: {e}", "rows": [], "rowCount": 0}

    clauses: list[str] = []
    bind_params: list[Any] = []

    if whereExpr:
        clauses.append(f"({whereExpr})")
        bind_params.extend(whereParams or [])

    for f in (extraFilters or []):
        if not isinstance(f, dict):
            continue
        col = f.get("column")
        val = f.get("value", None)
        op = (f.get("op") or "=").upper() if isinstance(f.get("op"), str) else "="
        # Skip entries whose value is None — this is the "optional filter
        # not provided" case.
        if val is None:
            continue
        if not isinstance(col, str) or not _COLUMN_NAME_RE.match(col):
            return {"error": f"db.select: invalid filter column name {col!r}",
                    "rows": [], "rowCount": 0}
        if op not in _ALLOWED_FILTER_OPS:
            return {"error": f"db.select: invalid filter op {op!r}",
                    "rows": [], "rowCount": 0}
        clauses.append(f"{col} {op} %s")
        bind_params.append(val)

    sql_text = f"SELECT {cols_raw} FROM {table}"
    if clauses:
        sql_text += " WHERE " + " AND ".join(clauses)
    if orderBy:
        sql_text += f" ORDER BY {orderBy}"
    sql_text += f" LIMIT {int(max(1, min(limit, 1000)))}"
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql_text, tuple(bind_params))
            col_names = [d[0] for d in []] if [] else []
            raw = _res or []

        # LangServer serialises task output back to Zeebe via json.dumps, which
        # fails on psycopg2 types that aren't JSON-native (date / datetime /
        # Decimal / bytes). Coerce them at the primitive boundary so the
        # downstream BPMN flow sees a flat JSON-serialisable payload.
        import datetime
        from decimal import Decimal
        def _coerce(v: Any) -> Any:
            if isinstance(v, (datetime.date, datetime.datetime)):
                return v.isoformat()
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, (bytes, bytearray)):
                try:
                    return v.decode("utf-8")
                except UnicodeDecodeError:
                    import base64
                    return base64.b64encode(v).decode("ascii")
            return v

        rows = [{k: _coerce(v) for k, v in dict(zip(col_names, r)).items()}
                for r in raw]
        return {"rows": rows, "rowCount": len(rows)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"db.select failed: {e}", "rows": [], "rowCount": 0}


_COLUMN_TYPE_CACHE: dict[str, dict[str, str]] = {}


def _load_column_types(table: str) -> dict[str, str]:
    """Return {column_name: data_type} for `table`. Cached per-process but
    only after a non-empty lookup — a freshly-created table may not yet be
    visible to information_schema on the specific pooled connection we
    grabbed, so we retry on later calls until we see the columns."""
    cached = _COLUMN_TYPE_CACHE.get(table)
    if cached:
        return cached
    rows: list = []
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = %s",
                (table,),
            )
            if []:
                rows = _res
    except Exception:
        rows = []
    m = {r[0]: r[1] for r in rows}
    if m:
        _COLUMN_TYPE_CACHE[table] = m
    return m


def _coerce_insert_values(table: str, values: dict) -> dict:
    types = _load_column_types(table)
    out: dict = {}
    for k, v in values.items():
        t = types.get(k, "")
        if v is None:
            out[k] = v
            continue
        try:
            if t in ("integer", "bigint", "smallint", "int"):
                out[k] = int(v) if not isinstance(v, bool) else int(v)
            elif t in ("double precision", "real", "numeric"):
                out[k] = float(v)
            elif t == "boolean":
                if isinstance(v, bool):
                    out[k] = v
                elif isinstance(v, str):
                    out[k] = v.lower() in ("true", "1", "t", "yes")
                else:
                    out[k] = bool(v)
            else:
                out[k] = str(v) if not isinstance(v, str) else v
        except (ValueError, TypeError):
            out[k] = v
    return out


async def task_generic_db_insert(sql: str = "", params: list | None = None,
                                 table: str = "",
                                 values: dict | None = None,
                                 row: dict | None = None,
                                 onConflict: str = "ignore",
                                 _bpmnProcessId: str = "") -> dict:
    """INSERT/UPDATE/DELETE primitive.

    Raw SQL path (BPMN-as-actor): `sql` is a full DML statement using
    PostgreSQL $1/$2/... placeholders; `params` is the ordered list of
    bind values. Used by BPMN actors that need UPDATE or complex INSERT
    (e.g. advance cursor, write embedding).

    Legacy table path: `table` + `values` dict generates an INSERT.
    `onConflict` controls duplicate handling.

    `_bpmnProcessId` is injected by the dispatcher.
    """
    import re as _re

    # Raw SQL path: full DML statement with $N placeholders.
    if sql:
        _param_list = list(params or [])
        _indices = [int(m.group(1)) for m in _re.finditer(r"\$(\d+)", sql)]
        psycopg_sql = _re.sub(r"\$\d+", "%s", sql)
        bind = [_param_list[i - 1] for i in _indices] if _indices else _param_list
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(psycopg_sql, tuple(bind))
                affected = (len(_res) if isinstance(_res, list) else 1) if (len(_res) if isinstance(_res, list) else 1) is not None else 0
            return {"updated": affected, "inserted": affected}
        except Exception as e:  # noqa: BLE001
            return {"error": f"db.insert failed: {e}", "updated": 0, "inserted": 0}

    if not table:
        return {"error": "table required"}
    _check_table(table)
    err = _enforce_write_scope(table, _bpmnProcessId)
    if err:
        return {"error": err, "inserted": 0}
    # Accept `row` as alias for `values` (ingestDocument BPMN uses `row`).
    if not values and row and isinstance(row, dict):
        values = row
    # Treat "skip" as equivalent to "ignore".
    if onConflict == "skip":
        onConflict = "ignore"
    if not values or not isinstance(values, dict):
        return {"error": "values required as dict"}

    # Strip None-valued columns. RisingWave cannot infer a typed NULL from
    # psycopg2's unknown-type binding and fails prepare-time type checks on
    # nullable numeric/boolean columns. Omitting the column entirely is
    # equivalent (nullable column defaults to NULL) and keeps optional
    # inputs well-behaved across the FEEL → LangServer → RW boundary.
    values = {k: v for k, v in values.items() if v is not None}
    if not values:
        return {"error": "all values are null after null-strip", "inserted": 0}

    # Coerce values to column types. Zeebe FEEL passes numerics through the
    # LangServer job wire in a way that sometimes lands as str in our dict;
    # RW's prepare-time type check rejects varchar→int/double assigns. We
    # look up the target column type via information_schema and cast.
    try:
        values = _coerce_insert_values(table, values)
    except Exception as e:  # noqa: BLE001
        return {"error": f"db.insert coerce failed: {e}", "inserted": 0}

    cols = list(values.keys())
    col_list = ", ".join(cols)
    params = [values[c] for c in cols]

    # RW prepare-time type check is strict: string params in `INSERT ... SELECT`
    # pattern don't implicitly cast to numeric targets. Emit typed placeholders
    # (`%s::<sql_type>`) derived from information_schema to keep the SELECT
    # path honest.
    types = _load_column_types(table)
    def _sql_type(col: str) -> str:
        t = types.get(col, "")
        if t in ("integer", "int"): return "integer"
        if t == "bigint": return "bigint"
        if t == "smallint": return "smallint"
        if t == "double precision": return "double precision"
        if t == "real": return "real"
        if t == "numeric": return "numeric"
        if t == "boolean": return "boolean"
        if t == "date": return "date"
        return "varchar"
    typed_placeholders = ", ".join(f"%s::{_sql_type(c)}" for c in cols)

    if onConflict == "ignore" and "vertex_id" in values:
        sql_text = (
            f"INSERT INTO {table} ({col_list}) "
            f"SELECT {typed_placeholders} "
            f"WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE vertex_id = %s::varchar)"
        )
        params.append(values["vertex_id"])
    else:
        sql_text = f"INSERT INTO {table} ({col_list}) VALUES ({typed_placeholders})"

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql_text, tuple(params))
            inserted = (len(_res) if isinstance(_res, list) else 1)
        # Return vertex_id and already_known for ingestDocument BPMN output mapping.
        vid = values.get("vertex_id", "")
        return {"inserted": inserted, "table": table,
                "vertex_id": vid, "already_known": inserted == 0}
    except Exception as e:  # noqa: BLE001
        return {"error": f"db.insert failed: {e}", "inserted": 0}


async def task_generic_db_purge_fuyou_pii(rows: list | None = None) -> dict:
    """Hard-delete Tier 3 fuyou rows and mark Tier 1 rows as purged.

    Per-batch atomic: DELETE pii + UPDATE meta status='purged' for each
    vertex_id. Implementation now shared with the EPFO/ESIC/ITR-1/GSTR-3B
    purge primitives via `_purge_pair`.
    """
    return await _purge_pair(
        rows,
        pii_table="vertex_fuyou_declaration_pii",
        meta_table="vertex_fuyou_declaration",
        primitive="db.purgeFuyouPii",
    )


async def task_generic_db_purge_epfo_pii(rows: list | None = None) -> dict:
    """Hard-delete Tier 3 EPFO rows and mark Tier 1 rows as purged."""
    return await _purge_pair(
        rows,
        pii_table="vertex_epfo_ecr_pii",
        meta_table="vertex_epfo_ecr",
        primitive="db.purgeEpfoPii",
    )


async def task_generic_db_purge_esic_pii(rows: list | None = None) -> dict:
    """Hard-delete Tier 3 ESIC rows and mark Tier 1 rows as purged."""
    return await _purge_pair(
        rows,
        pii_table="vertex_esic_contribution_pii",
        meta_table="vertex_esic_contribution",
        primitive="db.purgeEsicPii",
    )


async def task_generic_db_purge_itr1_pii(rows: list | None = None) -> dict:
    """Hard-delete Tier 3 ITR-1 rows and mark Tier 1 rows as purged."""
    return await _purge_pair(
        rows,
        pii_table="vertex_itr1_return_pii",
        meta_table="vertex_itr1_return",
        primitive="db.purgeItr1Pii",
    )


async def task_generic_db_purge_gstr3b_pii(rows: list | None = None) -> dict:
    """Hard-delete Tier 3 GSTR-3B rows and mark Tier 1 rows as purged."""
    return await _purge_pair(
        rows,
        pii_table="vertex_gstr3b_return_pii",
        meta_table="vertex_gstr3b_return",
        primitive="db.purgeGstr3bPii",
    )


async def task_generic_db_purge_seiyaku_confidential(rows: list | None = None) -> dict:
    """Hard-delete confidential open-seiyaku rows and mark Tier 1 rows as purged."""
    return await _purge_pair(
        rows,
        pii_table="vertex_open_seiyaku_batch_confidential",
        meta_table="vertex_open_seiyaku_batch",
        primitive="db.purgeSeiyakuConfidential",
    )


async def task_generic_db_bulk_insert(table: str = "", rows: list | None = None,
                                      _bpmnProcessId: str = "") -> dict:
    """Batch INSERT multiple rows into a table in a single VALUES statement (1-RTT).

    Intended for high-throughput BPMN pipelines (e.g. coverage.inferIngest)
    that push pre-validated row batches from the caller. All rows must share
    the same column set (derived from the first row).

    Returns: {"inserted": N, "table": table}
    """
    if not table:
        return {"error": "table required", "inserted": 0}
    _check_table(table)
    err = _enforce_write_scope(table, _bpmnProcessId)
    if err:
        return {"error": err, "inserted": 0}
    if not rows or not isinstance(rows, list):
        return {"inserted": 0, "table": table}

    clean_rows: list[dict] = []
    for r in rows:
        if isinstance(r, dict):
            clean_rows.append({k: v for k, v in r.items() if v is not None})
    if not clean_rows:
        return {"inserted": 0, "table": table}

    # Derive columns from the first row; all rows must share the same keys.
    cols = list(clean_rows[0].keys())
    col_list = ", ".join(cols)

    # Build multi-row VALUES with per-column type casts using the same
    # _sql_type lookup as generic.db.insert. Each call has a different number
    # of rows, so psycopg3 cannot promote to a reusable prepared statement.
    types = _load_column_types(table)

    def _sql_type(col: str) -> str:
        t = types.get(col, "")
        if t in ("integer", "int"): return "integer"
        if t == "bigint": return "bigint"
        if t == "smallint": return "smallint"
        if t == "double precision": return "double precision"
        if t == "real": return "real"
        if t == "numeric": return "numeric"
        if t == "boolean": return "boolean"
        if t == "date": return "date"
        return "varchar"

    row_placeholder = "(" + ", ".join(f"%s::{_sql_type(c)}" for c in cols) + ")"
    all_placeholders = ", ".join([row_placeholder] * len(clean_rows))
    sql_text = f"INSERT INTO {table} ({col_list}) VALUES {all_placeholders}"
    params: list = []
    for r in clean_rows:
        for c in cols:
            params.append(r.get(c))

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql_text, tuple(params))
            inserted = max(0, (len(_res) if isinstance(_res, list) else 1))
        return {"inserted": inserted, "table": table}
    except Exception as e:  # noqa: BLE001
        return {"error": f"db.bulkInsert failed: {e}", "inserted": 0}


async def task_generic_db_purge_datacenter_access_pii(rows: list | None = None) -> dict:
    """Hard-delete expired vertex_datacenter_access_request_pii rows.

    Inputs: rows — list of {vertex_id, facility_id, ...} objects returned by
    a preceding generic.db.select step.
    Returns: {"deleted": N}
    """
    if not rows:
        return {"deleted": 0}
    deleted = 0
    try:
        if True:
            client = get_kotoba_client()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                vertex_id = str(row.get("vertex_id") or "")
                if not vertex_id or not _VID_RE.fullmatch(vertex_id):
                    continue
                _res = client.q(
                    "DELETE FROM vertex_datacenter_access_request_pii WHERE vertex_id = %s",
                    (vertex_id,),
                )
                deleted += max(0, (len(_res) if isinstance(_res, list) else 1))
    except Exception as e:  # noqa: BLE001
        return {"error": f"db.purgeDatacenterAccessPii failed: {e}", "deleted": deleted}
    return {"deleted": deleted}


# ─── Shared helper for purge pair (Tier 3 DELETE + Tier 1 status='purged') ──

_VID_RE = re.compile(r"[A-Za-z0-9:_./%@\-]+")


async def _purge_pair(rows: list | None, *, pii_table: str, meta_table: str,
                      primitive: str) -> dict:
    """DELETE from pii_table + UPDATE meta_table.status='purged' per
    vertex_id in `rows`. table names are caller-fixed (not row-derived)
    so this is safe against vertex_id injection."""
    if not rows:
        return {"deleted": 0, "updated": 0}
    deleted = 0
    updated = 0
    try:
        if True:
            client = get_kotoba_client()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                vertex_id = str(row.get("vertex_id") or "")
                if not vertex_id or not _VID_RE.fullmatch(vertex_id):
                    continue
                _res = client.q(
                    f"DELETE FROM {pii_table} WHERE vertex_id = %s",
                    (vertex_id,),
                )
                deleted += max(0, (len(_res) if isinstance(_res, list) else 1))
                _res = client.q(
                    f"UPDATE {meta_table} SET status = %s "
                    "WHERE vertex_id = %s AND status != %s",
                    ("purged", vertex_id, "purged"),
                )
                updated += max(0, (len(_res) if isinstance(_res, list) else 1))
        return {"deleted": deleted, "updated": updated}
    except Exception as e:  # noqa: BLE001
        return {
            "error": f"{primitive} failed: {e}",
            "deleted": deleted,
            "updated": updated,
        }


async def task_generic_db_delete(table: str = "", whereExpr: str = "",
                                 whereParams: list | None = None) -> dict:
    """Generic DELETE primitive used by adopted (gyosei) BPMN.

    Same allowlist as `task_generic_db_select` — only `vertex_*`/`edge_*`/
    `mv_*` table names accepted. whereExpr is interpolated with %s
    placeholders bound to `whereParams`. If `whereExpr` is empty the
    primitive is a no-op (refuses to drop the whole table).
    """
    if not table:
        return {"error": "table required", "deleted": 0}
    if not _ALLOWED_TABLE_RE.fullmatch(table):
        return {"error": f"table {table!r} not in allowlist", "deleted": 0}
    if not whereExpr.strip():
        return {"error": "whereExpr required (refusing full-table delete)", "deleted": 0}
    params = tuple(whereParams or [])
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"DELETE FROM {table} WHERE {whereExpr}",
                params,
            )
            return {"deleted": max(0, (len(_res) if isinstance(_res, list) else 1))}
    except Exception as e:  # noqa: BLE001
        return {"error": f"db.delete failed: {e}", "deleted": 0}


async def task_generic_llm_chat(tier: str = "fast", system: str = "",
                                user: str = "", maxTokens: int = 400,
                                temperature: float = 0.3) -> dict:
    """Free-form chat primitive — same wire as task_chat but exposed
    under the generic.* namespace so BPMN authors don't need to know
    Devstral exists."""
    if not user:
        return {"error": "user prompt required"}
    try:
        resp = llm.call_tier(tier, system=system or "You are concise.",
                             user=user,
                             max_tokens=int(maxTokens),
                             temperature=float(temperature))
    except llm.LlmError as e:
        return {"error": str(e)}
    return {
        "content": resp["content"],
        "model": resp["model"],
        "latencyMs": resp["latencyMs"],
        "attempts": resp["attempts"],
        "usage": resp["usage"],
    }


async def task_generic_llm_json(tier: str = "classifier", system: str = "",
                                user: str = "", maxTokens: int = 600,
                                temperature: float = 0.1) -> dict:
    """LLM that must return ONE JSON object. BPMN gets the parsed
    object back as `data` (or error envelope on parse failure)."""
    if not user:
        return {"error": "user prompt required"}
    if not system:
        system = ("Output ONE JSON object. No preamble, no commentary, "
                  "no code fences.")
    result = llm.call_tier_json(tier, system=system, user=user,
                                max_tokens=int(maxTokens),
                                temperature=float(temperature))
    return result  # already shaped {ok,data,model,...} or {ok:False,error,...}


async def task_generic_rules_evaluate(ruleSet: str = "", facts: Any = None) -> dict:
    """Small deterministic rules primitive for BPMN guard tasks.

    This intentionally covers operational gates that are already encoded in
    BPMN models. Anything requiring dynamic policy loading should get its own
    reviewed primitive rather than expanding this generic surface.
    """
    rule_set = (ruleSet or "").strip()
    data = facts if isinstance(facts, dict) else {}
    findings: list[dict[str, Any]] = []

    def add(code: str, severity: str, message: str) -> None:
        findings.append({"code": code, "severity": severity, "message": message})

    if rule_set == "open-logistics-lastmile.dispatch.v1":
        missing = [
            key for key in ("vertexId", "legId", "carrierScheduleVid", "mode", "destAddress")
            if not data.get(key)
        ]
        for key in missing:
            add(f"missing.{key}", "error", f"{key} is required")
        sla_minutes = data.get("slaMinutes")
        try:
            sla_value = int(sla_minutes) if sla_minutes is not None else None
        except (TypeError, ValueError):
            sla_value = None
            add("invalid.slaMinutes", "error", "slaMinutes must be numeric")
        if sla_value is not None and sla_value <= 0:
            add("invalid.slaMinutes", "error", "slaMinutes must be positive")
        controlled = bool(data.get("temperatureRequired")) or bool(data.get("hazardousGoods"))
        return {
            "passed": not any(item["severity"] == "error" for item in findings),
            "findings": findings,
            "exceptionTier": "controlled" if controlled else "normal",
        }

    if rule_set == "open-logistics-lastmile.special-handling.v1":
        controlled = bool(data.get("temperatureRequired")) or bool(data.get("hazardousGoods"))
        if controlled and not data.get("carrierScheduleVid"):
            add("missing.carrierScheduleVid", "error", "controlled shipment needs carrier schedule")
        return {
            "passed": not any(item["severity"] == "error" for item in findings),
            "findings": findings,
            "exceptionTier": "controlled" if controlled else "normal",
        }

    if rule_set == "open-logistics-lastmile.delivery-proof.v1":
        minutes_late = data.get("minutesLate")
        try:
            late = int(minutes_late) if minutes_late is not None else 0
        except (TypeError, ValueError):
            late = 0
            add("invalid.minutesLate", "warning", "minutesLate should be numeric")
        damage = bool(data.get("damageReported"))
        proof_valid = bool(data.get("signatureCid")) or bool(data.get("deliveredAt"))
        if not proof_valid:
            add("missing.proof", "error", "signatureCid or deliveredAt is required")
        sla_tier = "damaged" if damage else "late" if late > 60 else "mild_late" if late > 0 else "on_time"
        return {
            "passed": not any(item["severity"] == "error" for item in findings),
            "proofValid": proof_valid,
            "slaTier": sla_tier,
            "claimRequired": damage or late > 60,
            "findings": findings,
        }

    if rule_set == "open-machinery-maintenance.plan.v1":
        missing = [key for key in ("vertexId", "assetId", "maintenanceType") if not data.get(key)]
        for key in missing:
            add(f"missing.{key}", "error", f"{key} is required")
        criticality = str(data.get("criticality") or "").lower()
        safety_lockout = bool(data.get("safetyLockout"))
        spare_parts_ready = bool(data.get("sparePartsReady"))
        if criticality == "high" and not safety_lockout:
            add("missing.safetyLockout", "error", "high criticality maintenance requires lockout")
        if not spare_parts_ready:
            add("review.spareParts", "warning", "spare parts are not confirmed ready")
        accepted = not any(item["severity"] == "error" for item in findings)
        return {
            "passed": accepted,
            "planAccepted": accepted,
            "riskTier": "controlled" if criticality == "high" else "standard",
            "findings": findings,
        }

    if rule_set == "open-machinery-maintenance.downtime.v1":
        estimated = data.get("estimatedMinutes")
        try:
            minutes = int(estimated) if estimated is not None else 0
        except (TypeError, ValueError):
            minutes = 0
            add("invalid.estimatedMinutes", "warning", "estimatedMinutes should be numeric")
        safety = bool(data.get("safetyIncident"))
        impact = str(data.get("productionImpact") or "")
        severity = "critical" if safety else "major" if minutes > 240 else "minor"
        escalation = safety or minutes > 240 or impact == "line_stop"
        return {
            "passed": True,
            "severity": severity,
            "escalationRequired": escalation,
            "findings": findings,
        }

    add("unknown.ruleSet", "warning", f"unknown ruleSet: {rule_set or '<empty>'}")
    return {"passed": True, "findings": findings}


# ─── Ethereum-anchored runtime receipt helpers ──────────────────────────

_ACTOR_RUNTIME_REGISTRY_ADDR = os.environ.get("ACTOR_RUNTIME_REGISTRY_ADDR", "").strip()
_ACTOR_RUNTIME_RPC_URL = os.environ.get("ACTOR_RUNTIME_RPC_URL", os.environ.get("ETH_RPC_URL", "")).strip()


def _bytes32_hex(value: str, *, field: str) -> str:
    raw = (value or "").strip()
    if raw.startswith("0x") and len(raw) == 66:
        return raw
    if not raw:
        raise ValueError(f"{field} required")
    return "0x" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "0x" + hashlib.sha256(encoded).hexdigest()


async def _maybe_record_runtime_receipt(
    *,
    job_id: str,
    actor_did: str,
    artifact_id: str,
    input_hash: str,
    output_hash: str,
    trace_hash: str,
    operator_did: str,
    started_at: int,
    finished_at: int,
) -> dict[str, Any]:
    """Best-effort EVM receipt submit; returns calldata values if skipped."""
    if not _ACTOR_RUNTIME_REGISTRY_ADDR or not _ACTOR_RUNTIME_RPC_URL or not os.environ.get("PRIVATE_KEY"):
        return {"submitted": False, "reason": "actor-runtime-chain-env-missing"}

    cmd = [
        "cast",
        "send",
        _ACTOR_RUNTIME_REGISTRY_ADDR,
        "recordExecutionReceipt(bytes32,bytes32,bytes32,bytes32,bytes32,bytes32,bytes32,uint64,uint64)",
        job_id,
        actor_did,
        artifact_id,
        input_hash,
        output_hash,
        trace_hash,
        operator_did,
        str(started_at),
        str(finished_at),
        "--rpc-url",
        _ACTOR_RUNTIME_RPC_URL,
        "--private-key",
        os.environ["PRIVATE_KEY"],
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=45)
    except (FileNotFoundError, PermissionError) as e:
        return {"submitted": False, "reason": f"cast-unavailable: {e}"}
    except asyncio.TimeoutError:
        return {"submitted": False, "reason": "cast-timeout"}

    return {
        "submitted": proc.returncode == 0,
        "exitCode": proc.returncode,
        "stdout": (stdout or b"").decode(errors="replace")[-2000:],
        "stderr": (stderr or b"").decode(errors="replace")[-2000:],
    }



# ─── F1+ : pds / http / audit primitives ─────────────────────────────────

import urllib.error as _u_err  # noqa: E402  (kept beside use site)
import urllib.request as _u_req  # noqa: E402

_PDS_BASE = os.environ.get("PDS_URL", "https://atproto.etzhayyim.com")
_PDS_SERVICE_AUTH_TOKEN = os.environ.get("PDS_SERVICE_AUTH_TOKEN", "").strip()
_PDS_SERVICE_AUTH_MINT_URL = os.environ.get(
    "PDS_SERVICE_AUTH_MINT_URL",
    f"{_PDS_BASE}/_internal/mint-pds-bearer",
).strip()
_PDS_SERVICE_AUTH_MINT_SECRET = os.environ.get("PDS_SERVICE_AUTH_MINT_SECRET", "").strip()
try:
    _PDS_SERVICE_AUTH_TTL_SEC = int(os.environ.get("PDS_SERVICE_AUTH_TTL_SEC", "600"))
except ValueError:
    _PDS_SERVICE_AUTH_TTL_SEC = 600
_PDS_SERVICE_AUTH_TTL_SEC = max(30, min(600, _PDS_SERVICE_AUTH_TTL_SEC))
_PDS_LEGACY_INTERNAL_TRUST = os.environ.get("PDS_LEGACY_INTERNAL_TRUST", "0") == "1"
_PDS_PREFER_LEGACY_TRUST_FOR_REPO_WRITE = (
    os.environ.get("PDS_PREFER_LEGACY_TRUST_FOR_REPO_WRITE", "0") == "1"
)
# ADR-2604282300: Zeebe/UDF/LangGraph must NOT route through CF Workers.
# Social/AT writes use the C-path (direct vertex_repo_record INSERT).
# com.etzhayyim.* XRPC calls route to bpmn-dispatcher K8s ClusterIP directly.
_BPMN_DISPATCHER_INTERNAL_URL = os.environ.get(
    "BPMN_DISPATCHER_INTERNAL_URL",
    "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
).rstrip("/")
_BPMN_DISPATCHER_INTERNAL_SECRET = os.environ.get("BPMN_DISPATCHER_INTERNAL_SECRET", "").strip()
_AT_SOCIAL_NSID_PREFIXES = ("app.bsky.", "chat.bsky.", "com.atproto.repo.")
_etzhayyim_APP_NSID_PREFIX = "com.etzhayyim."
_COMFYUI_BASE = os.environ.get("COMFYUI_URL", "https://comfyui.etzhayyim.com")
_COMFYUI_KEY = os.environ.get("COMFYUI_API_KEY", "")
_COMFYUI_BLOB_REPO = os.environ.get("COMFYUI_BLOB_REPO", "did:web:animeka.etzhayyim.com")
# Phase Δ3 Task 1 — Serverless mode. Set to "serverless" to route
# /v1/images/generations through RunPod Serverless /runsync instead of
# the comfyui.etzhayyim.com passthrough. Auto-detected when COMFYUI_URL
# contains "api.runpod.ai".
_COMFYUI_SHAPE = os.environ.get(
    "COMFYUI_UPSTREAM_SHAPE",
    "serverless" if "api.runpod.ai" in _COMFYUI_BASE else "gateway",
)
# Default checkpoint for workflow builder. Override per-call via body.model.
_COMFYUI_DEFAULT_CKPT = os.environ.get(
    "COMFYUI_DEFAULT_CKPT", "animagine-xl-4.0.safetensors"
)
_PD_COLOR_MEDIA_ROUTES = {
    "/v1/video/shot-segmentation",
    "/v1/video/restore",
    "/v1/video/colorize",
    "/v1/video/enhance-quality",
    "/v1/video/encode-publication-package",
    "/v1/audio/transcribe-and-align",
    "/v1/audio/dub-localized-speech",
    "/v1/video/mux-localized-publication-package",
}


def _http_post_json(url: str, payload: dict, headers: dict, timeout: float = 30.0) -> tuple[int, dict | str]:
    body = json.dumps(payload).encode("utf-8")
    merged_headers = {"User-Agent": "etzhayyim-kotodama-zeebe/0.2"}
    merged_headers.update(headers)
    req = _u_req.Request(url, data=body, headers=merged_headers, method="POST")
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except _u_err.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return -1, {"error": f"transport: {e}"}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw.decode("utf-8", errors="replace")[:500]}


_PDS_SERVICE_AUTH_CACHE: dict[str, dict[str, Any]] = {}


def _mint_pds_service_auth(lxm: str) -> str:
    cached = _PDS_SERVICE_AUTH_CACHE.get(lxm)
    now = int(time.time())
    if cached and int(cached.get("expiresAt", 0)) > now + 30:
        token = str(cached.get("token") or "")
        if token:
            return token

    if not _PDS_SERVICE_AUTH_MINT_URL or not _PDS_SERVICE_AUTH_MINT_SECRET:
        return ""

    payload = {"lxm": lxm, "ttlSeconds": _PDS_SERVICE_AUTH_TTL_SEC}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_PDS_SERVICE_AUTH_MINT_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-bpmn-auth": sig,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
    }
    req = _u_req.Request(_PDS_SERVICE_AUTH_MINT_URL, data=body, headers=headers, method="POST")
    try:
        with _u_req.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except _u_err.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")[:300]
        LOG.warning("PDS service auth mint failed: status=%s body=%s", e.code, raw)
        return ""
    except Exception as e:  # noqa: BLE001
        LOG.warning("PDS service auth mint transport error: %s", e)
        return ""

    token = str(data.get("token") or "")
    expires_at = int(data.get("expiresAt") or (now + _PDS_SERVICE_AUTH_TTL_SEC))
    if token:
        _PDS_SERVICE_AUTH_CACHE[lxm] = {"token": token, "expiresAt": expires_at}
    return token


def _internal_trust_hmac_header(path: str) -> str:
    if not _PDS_SERVICE_AUTH_MINT_SECRET:
        return ""
    minute = int(time.time() * 1000 // 60_000)
    signing_input = f"POST:{path}:{minute}".encode("utf-8")
    digest = hmac.new(
        _PDS_SERVICE_AUTH_MINT_SECRET.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


async def _pds_dispatch_c_path(
    type: str, payload: dict, callerDid: str, started: float
) -> dict:
    """C-path: write social/AT record directly to vertex_repo_record.

    Graph-visible but not federable (no AT Protocol MST commit / firehose).
    Eliminates the CF edge round-trip for social writes per ADR-2604282300.
    """
    from kotodama.primitives.yoro_social import build_repo_record, insert_social_post_record  # noqa: PLC0415

    if type == "app.bsky.feed.post":
        repo = str(payload.get("repo") or callerDid or "did:web:yoro.etzhayyim.com")
        collection = "app.bsky.feed.post"
        record = {k: v for k, v in payload.items() if k != "repo"}
        record.setdefault("$type", collection)
        if "createdAt" not in record:
            import datetime as _dt  # noqa: PLC0415
            record["createdAt"] = (
                _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            )
    else:
        repo = str(payload.get("repo") or callerDid or "did:web:yoro.etzhayyim.com")
        collection = str(payload.get("collection") or type)
        raw_record = payload.get("record")
        if raw_record is None and payload.get("recordJson"):
            try:
                raw_record = json.loads(str(payload["recordJson"]))
            except (json.JSONDecodeError, TypeError):
                raw_record = {}
        record = raw_record if isinstance(raw_record, dict) else {}

    rkey = str(payload.get("rkey") or "")
    row = build_repo_record(repo=repo, collection=collection, record=record, rkey=rkey)
    result = await asyncio.to_thread(insert_social_post_record, row, flush=False)
    return {
        "status": 200,
        "body": result,
        "cid": row["cid"],
        "uri": row["uri"],
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


async def _pds_dispatch_internal_xrpc(type: str, payload: dict, started: float) -> dict:
    """Route com.etzhayyim.* XRPC to bpmn-dispatcher K8s ClusterIP (no CF edge hop)."""
    url = f"{_BPMN_DISPATCHER_INTERNAL_URL}/xrpc/{type}"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if _BPMN_DISPATCHER_INTERNAL_SECRET:
        headers["x-internal-trust"] = _BPMN_DISPATCHER_INTERNAL_SECRET
    status, body = await asyncio.to_thread(_http_post_json, url, payload, headers, 60.0)
    if status >= 400 or status < 0:
        raise RuntimeError(
            f"BPMN dispatcher XRPC failed: type={type} status={status} body={body}"
        )
    cid = body.get("cid") if isinstance(body, dict) else None
    uri = body.get("uri") if isinstance(body, dict) else None
    return {
        "status": status,
        "body": body,
        "cid": cid or "",
        "uri": uri or "",
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


async def _pds_dispatch_legacy(
    type: str, payload: dict, callerDid: str, started: float
) -> dict:
    """Legacy PDS HTTP fallback for non-etzhayyim, non-social NSIDs."""
    prefer_legacy_trust = (
        _PDS_LEGACY_INTERNAL_TRUST
        and _PDS_PREFER_LEGACY_TRUST_FOR_REPO_WRITE
        and type in {"com.atproto.repo.createRecord", "com.atproto.repo.putRecord", "com.atproto.repo.deleteRecord"}
    )
    minted_token = "" if prefer_legacy_trust else await asyncio.to_thread(_mint_pds_service_auth, type)
    bearer_token = "" if prefer_legacy_trust else (minted_token or _PDS_SERVICE_AUTH_TOKEN)
    if not bearer_token and not _PDS_LEGACY_INTERNAL_TRUST:
        return {
            "error": "PDS service auth mint or PDS_SERVICE_AUTH_TOKEN required for generic.pds.dispatch",
            "status": 401,
        }
    path = f"/xrpc/{type}"
    url = f"{_PDS_BASE}{path}"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif _PDS_LEGACY_INTERNAL_TRUST:
        headers["x-kotoba-kotodama-verified"] = "true"
        internal_hmac = _internal_trust_hmac_header(path)
        if internal_hmac:
            headers["x-etzhayyim-internal-hmac"] = internal_hmac
        active_did = str(payload.get("repo") or payload.get("did") or callerDid or "").strip()
        if active_did:
            headers["x-active-did"] = active_did
    status, body = await asyncio.to_thread(_http_post_json, url, payload, headers, 30.0)
    if status >= 400 or status < 0:
        raise RuntimeError(f"PDS dispatch failed: type={type} status={status} body={body}")
    cid = body.get("cid") if isinstance(body, dict) else None
    uri = body.get("uri") if isinstance(body, dict) else None
    return {
        "status": status,
        "body": body,
        "cid": cid or "",
        "uri": uri or "",
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


async def task_generic_pds_dispatch(type: str = "", payload: dict | None = None,
                                    callerDid: str = "") -> dict:
    """Route a record / social action within the K8s cluster (no CF edge round-trip).

    Routing per ADR-2604282300:
    - app.bsky.* / chat.bsky.* / com.atproto.repo.* → C-path: write
      vertex_repo_record directly (graph-visible, not federable).
    - com.etzhayyim.* → internal K8s bpmn-dispatcher POST with x-internal-trust.
    - Other NSIDs → legacy PDS HTTP call (backward compat fallback).
    """
    if not type:
        return {"error": "type (NSID) required"}
    payload = payload or {}
    if callerDid:
        payload.setdefault("did", callerDid)

    started = time.monotonic()

    if type.startswith(_AT_SOCIAL_NSID_PREFIXES):
        return await _pds_dispatch_c_path(type, payload, callerDid, started)

    if type.startswith(_etzhayyim_APP_NSID_PREFIX) and _BPMN_DISPATCHER_INTERNAL_URL:
        return await _pds_dispatch_internal_xrpc(type, payload, started)

    return await _pds_dispatch_legacy(type, payload, callerDid, started)


_XRPC_NSID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+$")


_PD_COLOR_XRPC_NSIDS = {
    "com.etzhayyim.apps.storage.resolveSourceAsset",
    "com.etzhayyim.apps.copyright.license.inspect",
    "com.etzhayyim.apps.i18n.translateBatch",
}


async def _pd_color_add_json_manifest(kind: str, payload: dict) -> str:
    from kotodama.primitives import ipfs_ingest  # noqa: PLC0415

    body = json.dumps(
        {
            "kind": kind,
            "schema": "com.etzhayyim.apps.publicDomainColorization.manifest.v1",
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return await ipfs_ingest.add_content(body, f"{kind}.json")


async def _pd_color_local_xrpc(nsid: str, payload: dict) -> dict:
    """Local XRPC-compatible implementation for the public-domain color demo.

    These handlers let the Zeebe process run before dedicated storage,
    copyright, and i18n actors are deployed. Outputs intentionally match the
    BPMN's `response.*` mappings.
    """
    if nsid == "com.etzhayyim.apps.storage.resolveSourceAsset":
        source_record = {
            "workId": payload.get("workId"),
            "title": payload.get("title"),
            "workKind": payload.get("workKind"),
            "sourceUrl": payload.get("sourceUrl"),
            "sourceBlobCid": payload.get("sourceBlobCid"),
            "sourceIpfsCid": payload.get("sourceIpfsCid"),
            "sourceIpfsUrl": payload.get("sourceIpfsUrl"),
            "sourceSha256": payload.get("sourceSha256"),
            "sourceByteSize": payload.get("sourceByteSize"),
            "publishJurisdiction": payload.get("publishJurisdiction"),
            "sourceLanguage": payload.get("sourceLanguage"),
        }
        return {"status": 200, "response": source_record}

    if nsid == "com.etzhayyim.apps.copyright.license.inspect":
        source_record = payload.get("sourceRecord") if isinstance(payload.get("sourceRecord"), dict) else {}
        source_cid = str(
            payload.get("sourceIpfsCid")
            or source_record.get("sourceIpfsCid")
            or payload.get("sourceBlobCid")
            or source_record.get("sourceBlobCid")
            or ""
        )
        requested = str(payload.get("requestedLicense") or "").lower()
        jurisdiction = str(payload.get("publishJurisdiction") or "US")
        classification = "public-domain" if requested in ("pd-mark", "public-domain", "") else "manual-review"
        blocked_reasons: list[str] = []
        if jurisdiction != "US":
            classification = "manual-review"
            blocked_reasons.append("non_us_jurisdiction_requires_manual_review")
        evidence_payload = {
            "workId": payload.get("workId"),
            "title": payload.get("title"),
            "classification": classification,
            "blockedReasons": blocked_reasons,
            "sourceIpfsCid": source_cid,
            "publishJurisdiction": jurisdiction,
            "requestedLicense": requested or "pd-mark",
        }
        evidence_cid = await _pd_color_add_json_manifest("pd-color-rights-evidence", evidence_payload)
        return {
            "status": 200,
            "response": {
                "classification": classification,
                "evidenceCid": f"ipfs://{evidence_cid}",
                "blockedReasons": blocked_reasons,
            },
        }

    if nsid == "com.etzhayyim.apps.i18n.translateBatch":
        target_langs = payload.get("targetLangs") if isinstance(payload.get("targetLangs"), list) else []
        source_lang = str(payload.get("sourceLang") or "en")
        source_cid = str(payload.get("sourceCid") or "")
        manifest_payload = {
            "project": payload.get("project") or "public-domain-colorization",
            "contentKind": payload.get("contentKind") or "timed-text",
            "sourceLang": source_lang,
            "targetLangs": target_langs,
            "sourceCid": source_cid,
            "preserveTimestamps": bool(payload.get("preserveTimestamps", True)),
            "translations": [
                {
                    "lang": str(lang),
                    "sourceCid": source_cid,
                    "subtitleCid": source_cid,
                    "status": "placeholder_manifest_ready",
                }
                for lang in target_langs
            ],
            "context": payload.get("context") if isinstance(payload.get("context"), dict) else {},
        }
        manifest_cid = await _pd_color_add_json_manifest("pd-color-subtitle-manifest", manifest_payload)
        return {
            "status": 200,
            "response": {
                "manifestCid": manifest_cid,
                "translatedCount": len(target_langs),
                "languages": target_langs,
            },
        }

    return {"error": f"unsupported local pd-color nsid {nsid}", "status": 400}


def _xrpc_base_from_actor(actor: str) -> str:
    if not actor.startswith("did:web:"):
        return ""
    did_web_path = actor[len("did:web:"):].strip()
    if not did_web_path:
        return ""
    return "https://" + did_web_path.replace(":", "/").strip("/")


async def task_generic_xrpc_invoke(actor: str = "", nsid: str = "",
                                   payload: dict | None = None,
                                   baseUrl: str = "",
                                   headers: dict | None = None,
                                   timeoutSec: float = 45.0) -> dict:
    """Invoke an app XRPC endpoint from BPMN.

    Prefer `baseUrl` for explicit service routing. When omitted, a
    `did:web:host[:path]` actor resolves to `https://host[/path]/xrpc/{nsid}`.
    """
    nsid = (nsid or "").strip()
    if not nsid:
        return {"error": "nsid required", "status": 400}
    if not _XRPC_NSID_RE.match(nsid):
        return {"error": f"invalid nsid {nsid!r}", "status": 400}
    if nsid in _PD_COLOR_XRPC_NSIDS:
        return await _pd_color_local_xrpc(nsid, payload or {})
    base = (baseUrl or "").strip().rstrip("/") or _xrpc_base_from_actor(actor or "")
    if not base:
        return {"error": "baseUrl or did:web actor required", "status": 400}
    if not base.startswith(("https://", "http://")):
        return {"error": "baseUrl must include http(s) scheme", "status": 400}
    if not isinstance(payload, dict):
        payload = {}
    if actor:
        payload.setdefault("actor", actor)
    merged_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-kotoba-kotodama-verified": "true",
    }
    if headers:
        merged_headers.update({str(k): str(v) for k, v in headers.items()})
    timeout = max(1.0, min(float(timeoutSec or 45.0), 120.0))
    started = time.monotonic()
    status, body = await asyncio.to_thread(
        _http_post_json,
        f"{base}/xrpc/{nsid}",
        payload,
        merged_headers,
        timeout,
    )
    return {
        "status": status,
        "result": body,
        "response": body,
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


def _stable_vertex_suffix(value: dict) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


async def task_open_patent_expired_drug_patent_screen(payload: dict | None = None) -> dict:
    p = payload or {}
    as_of = str(p.get("asOf") or time.strftime("%Y-%m-%d", time.gmtime()))
    expiry_date = str(p.get("expiryDate") or "")
    blocking_until = str(p.get("blockingExclusivityUntil") or "")
    eligible = bool(expiry_date and expiry_date <= as_of and (not blocking_until or blocking_until <= as_of))
    status = "eligible" if eligible else "blocked_or_pending"
    seed = {
        "patentVertexId": p.get("patentVertexId"),
        "patentNumber": p.get("patentNumber"),
        "jurisdiction": p.get("jurisdiction"),
        "productId": p.get("productId"),
        "asOf": as_of,
    }
    vertex_id = str(p.get("patentVertexId") or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.expiredDrugPatentScreen/{_stable_vertex_suffix(seed)}")
    return {
        "vertexId": vertex_id,
        "eligible": eligible,
        "status": status,
        "asOf": as_of,
    }


async def task_open_patent_expired_drug_patent_collect(payload: dict | None = None) -> dict:
    p = payload or {}
    rows = p.get("rows") if isinstance(p.get("rows"), list) else []
    limit = int(p.get("limit") or len(rows) or 0)
    as_of = str(p.get("asOf") or time.strftime("%Y-%m-%d", time.gmtime()))
    jurisdiction = str(p.get("jurisdiction") or "")
    scoped_rows = rows[:limit] if limit > 0 else rows
    candidates = [
        row for row in scoped_rows
        if isinstance(row, dict)
        and str(row.get("expiryDate") or "") <= as_of
        and (not jurisdiction or str(row.get("jurisdiction") or "") == jurisdiction)
    ]
    run_seed = {
        "asOf": as_of,
        "jurisdiction": jurisdiction,
        "limit": limit,
        "rows": scoped_rows,
    }
    return {
        "runVertexId": f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.expiredDrugPatentBacklog/{_stable_vertex_suffix(run_seed)}",
        "scannedCount": len(scoped_rows),
        "candidateCount": len(candidates),
        "insertedCount": 0 if p.get("dryRun", True) else len(candidates),
    }


async def task_open_patent_generic_manufacturing_plan(payload: dict | None = None) -> dict:
    p = payload or {}
    seed = {
        "expiryScreenVid": p.get("expiryScreenVid"),
        "productId": p.get("productId"),
        "candidateKind": p.get("candidateKind"),
        "manufacturerOrgId": p.get("manufacturerOrgId"),
        "plantOrgId": p.get("plantOrgId"),
        "targetMarket": p.get("targetMarket"),
    }
    suffix = _stable_vertex_suffix(seed)
    return {
        "vertexId": f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.genericManufacturingCandidate/{suffix}",
        "seiyakuProcessId": f"seiyaku_generic_manufacturing_{suffix}",
        "status": "planned",
    }


async def task_open_patent_generic_manufacturing_prepare_seiyaku_batch_draft(payload: dict | None = None) -> dict:
    p = payload or {}
    product_code = str(p.get("productCode") or p.get("productId") or "generic-product")
    batch_number = str(p.get("batchNumber") or f"batch-{_stable_vertex_suffix({'handoffVid': p.get('handoffVid'), 'productCode': product_code})}")
    seed = {
        "handoffVid": p.get("handoffVid"),
        "productId": p.get("productId"),
        "manufacturerOrgId": p.get("manufacturerOrgId"),
        "plantOrgId": p.get("plantOrgId"),
        "batchNumber": batch_number,
    }
    vertex_id = str(
        p.get("vertexId")
        or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.seiyakuBatchDraft/{_stable_vertex_suffix(seed)}"
    )
    seiyaku_process_id = str(p.get("seiyakuProcessId") or "seiyaku_register_batch")
    batch_payload = {
        "handoffVid": p.get("handoffVid"),
        "productId": p.get("productId"),
        "manufacturerOrgId": p.get("manufacturerOrgId"),
        "plantOrgId": p.get("plantOrgId"),
        "productCode": product_code,
        "batchNumber": batch_number,
        "dosageForm": p.get("dosageForm") or "unspecified",
        "targetMarket": p.get("targetMarket") or "JPN",
    }
    return {
        "ok": True,
        "vertexId": vertex_id,
        "seiyakuProcessId": seiyaku_process_id,
        "batchNumber": batch_number,
        "status": "draft_ready",
        "batchPayload": batch_payload,
    }


async def task_open_patent_generic_manufacturing_validate_seiyaku_batch_draft(payload: dict | None = None) -> dict:
    p = payload or {}
    batch_payload = p.get("batchPayload") if isinstance(p.get("batchPayload"), dict) else {}
    required = {
        "manufacturerOrgId": p.get("manufacturerOrgId") or batch_payload.get("manufacturerOrgId"),
        "plantOrgId": p.get("plantOrgId") or batch_payload.get("plantOrgId"),
        "productCode": p.get("productCode") or batch_payload.get("productCode"),
        "batchNumber": p.get("batchNumber") or batch_payload.get("batchNumber"),
        "dosageForm": p.get("dosageForm") or batch_payload.get("dosageForm"),
        "targetMarket": p.get("targetMarket") or batch_payload.get("targetMarket"),
    }
    findings = [f"missing {name}" for name, value in required.items() if not str(value or "").strip()]
    passed = len(findings) == 0
    seed = {
        "batchDraftVid": p.get("batchDraftVid"),
        "batchNumber": required["batchNumber"],
        "findings": findings,
    }
    return {
        "ok": True,
        "vertexId": str(
            p.get("vertexId")
            or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.seiyakuBatchDraftValidation/{_stable_vertex_suffix(seed)}"
        ),
        "passed": passed,
        "status": "validated" if passed else "validation_failed",
        "findings": findings,
    }


async def task_open_patent_generic_manufacturing_handoff_seiyaku(payload: dict | None = None) -> dict:
    p = payload or {}
    seed = {
        "genericCandidateVid": p.get("genericCandidateVid"),
        "productId": p.get("productId"),
        "seiyakuProcessId": p.get("seiyakuProcessId"),
    }
    seiyaku_process_id = str(p.get("seiyakuProcessId") or f"seiyaku_generic_{_stable_vertex_suffix(seed)}")
    return {
        "vertexId": str(
            p.get("vertexId")
            or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.seiyakuHandoff/{_stable_vertex_suffix(seed)}"
        ),
        "seiyakuProcessId": seiyaku_process_id,
        "status": "handoff_queued",
    }


async def task_open_patent_generic_manufacturing_queue_seiyaku_batch_start(payload: dict | None = None) -> dict:
    p = payload or {}
    seed = {
        "batchDraftVid": p.get("batchDraftVid"),
        "validationVid": p.get("validationVid"),
    }
    batch_payload = p.get("batchPayload") if isinstance(p.get("batchPayload"), dict) else {}
    start_nsid = str(p.get("startNsid") or "com.etzhayyim.apps.openPatent.genericManufacturing.startSeiyakuBatch")
    bpmn_process_id = str(p.get("bpmnProcessId") or "seiyaku_register_batch")
    return {
        "vertexId": str(
            p.get("vertexId")
            or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.seiyakuBatchStartRequest/{_stable_vertex_suffix(seed)}"
        ),
        "startNsid": start_nsid,
        "bpmnProcessId": bpmn_process_id,
        "status": "queued" if p.get("validationPassed") else "skipped_invalid",
        "batchPayload": batch_payload,
    }


async def task_open_patent_generic_manufacturing_ack_seiyaku_batch_start(payload: dict | None = None) -> dict:
    p = payload or {}
    seed = {
        "startRequestVid": p.get("startRequestVid"),
        "seiyakuInstanceKey": p.get("seiyakuInstanceKey"),
        "seiyakuBatchVertexId": p.get("seiyakuBatchVertexId"),
        "status": p.get("status"),
    }
    return {
        "vertexId": str(
            p.get("vertexId")
            or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.seiyakuBatchStartAck/{_stable_vertex_suffix(seed)}"
        ),
        "status": str(p.get("status") or "acknowledged"),
        "startRequestVid": str(p.get("startRequestVid") or ""),
        "seiyakuInstanceKey": str(p.get("seiyakuInstanceKey") or ""),
        "seiyakuBatchVertexId": str(p.get("seiyakuBatchVertexId") or ""),
    }


async def task_open_patent_generic_manufacturing_summarize_seiyaku_start_progress(payload: dict | None = None) -> dict:
    p = payload or {}
    start_status = str(p.get("startRequestStatus") or "unknown")
    ack_status = str(p.get("ackStatus") or "unknown")
    if start_status in {"queued", "started"} and ack_status in {"acknowledged", "confirmed"}:
        progress_status = "in_progress"
    elif "failed" in start_status or "failed" in ack_status:
        progress_status = "failed"
    elif start_status == "completed" and ack_status in {"acknowledged", "confirmed"}:
        progress_status = "completed"
    else:
        progress_status = "pending"
    seed = {
        "startRequestVid": p.get("startRequestVid"),
        "ackVid": p.get("ackVid"),
        "progressStatus": progress_status,
    }
    return {
        "vertexId": str(
            p.get("vertexId")
            or f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.seiyakuStartProgress/{_stable_vertex_suffix(seed)}"
        ),
        "progressStatus": progress_status,
        "startRequestVid": str(p.get("startRequestVid") or ""),
        "ackVid": str(p.get("ackVid") or ""),
    }


async def task_open_patent_expired_drug_patent_record_blocker(payload: dict | None = None) -> dict:
    p = payload or {}
    as_of = str(p.get("asOf") or time.strftime("%Y-%m-%d", time.gmtime()))
    blocking_until = str(p.get("blockingUntil") or "")
    active = bool(blocking_until and blocking_until >= as_of)
    seed = {
        "patentVertexId": p.get("patentVertexId"),
        "patentNumber": p.get("patentNumber"),
        "jurisdiction": p.get("jurisdiction"),
        "productId": p.get("productId"),
        "blockerType": p.get("blockerType"),
        "blockingUntil": blocking_until,
        "source": p.get("source"),
        "evidenceUri": p.get("evidenceUri"),
    }
    return {
        "vertexId": f"at://did:web:open-patent.etzhayyim.com/com.etzhayyim.apps.openPatent.drugRegulatoryBlocker/{_stable_vertex_suffix(seed)}",
        "active": active,
        "status": "active" if active else "expired_or_unbounded",
        "blockingUntil": blocking_until,
    }


async def task_open_patent_expired_drug_patent_pipeline(payload: dict | None = None) -> dict:
    p = payload or {}
    rows = p.get("rows") if isinstance(p.get("rows"), list) else []
    as_of = str(p.get("asOf") or time.strftime("%Y-%m-%d", time.gmtime()))
    jurisdiction = str(p.get("jurisdiction") or "")
    collect = await task_open_patent_expired_drug_patent_collect(payload=p)
    plans: list[dict] = []
    screened = 0
    skipped = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if jurisdiction and str(row.get("jurisdiction") or "") != jurisdiction:
            continue
        screen_payload = {**row, "asOf": as_of}
        screen = await task_open_patent_expired_drug_patent_screen(payload=screen_payload)
        screened += 1
        if not screen.get("eligible"):
            skipped += 1
            continue
        if not row.get("productId"):
            skipped += 1
            continue
        plan = await task_open_patent_generic_manufacturing_plan(
            payload={
                **row,
                "expiryScreenVid": screen["vertexId"],
                "candidateKind": p.get("candidateKind") or "generic",
            }
        )
        plans.append(plan)
    return {
        "ok": True,
        "runVertexId": collect["runVertexId"],
        "asOf": as_of,
        "collectedCount": collect["candidateCount"],
        "screenedCount": screened,
        "plannedCount": len(plans),
        "skippedPlanCount": skipped,
        "plans": plans,
    }


_NEWS_XRPC_BASE = os.environ.get("NEWS_XRPC_BASE", "https://news.etzhayyim.com")


async def task_news_udf_score_intel(
    sourceType: str = "",
    official: bool = False,
    primary: bool = True,
    evidenceCount: int = 0,
    findingCount: int = 0,
    recencyHours: float = 24.0,
    impact: float = 0.5,
) -> dict:
    """Score a news intel brief using RisingWave external UDFs."""
    official_count = 1 if official else 0
    corroborated_count = max(0, int(findingCount or 0))
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                SELECT
                  news_source_credibility(%s, %s, %s) AS credibility,
                  news_intel_priority(%s, %s, %s, %s, %s) AS priority
                """,
                (
                    sourceType or "unknown",
                    bool(primary),
                    bool(official),
                    max(0, int(evidenceCount or 0)),
                    official_count,
                    corroborated_count,
                    float(recencyHours or 24.0),
                    float(impact or 0.5),
                ),
            )
            row = (_res[0] if _res else None)
        return {
            "credibility": float(row[0] if row else 0.5),
            "priority": float(row[1] if row else 0.4),
        }
    except Exception as e:  # noqa: BLE001
        LOG.warning("news.udf.scoreIntel failed; returning fallback score: %s", e)
        return {"credibility": 0.5, "priority": 0.4, "error": str(e)[:300]}


async def _news_xrpc(nsid: str, input: dict | None = None) -> dict:
    url = f"{_NEWS_XRPC_BASE.rstrip('/')}/xrpc/{nsid}"
    started = time.monotonic()
    status, body = await asyncio.to_thread(
        _http_post_json,
        url,
        input or {},
        {"Content-Type": "application/json", "x-kotoba-kotodama-verified": "true"},
        45.0,
    )
    return {
        "status": status,
        "result": body,
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


async def task_news_xrpc_analyze_intel(actor: str = "", input: dict | None = None) -> dict:
    """Call news.etzhayyim.com analyzeIntel from Zeebe BPMN."""
    payload = dict(input or {})
    # FEEL may materialise missing nested fields as non-JSON "unknown"
    # sentinel objects. The news Worker lexicon expects scalar strings.
    for key in list(payload.keys()):
        value = payload[key]
        if value is None:
            payload.pop(key, None)
        elif isinstance(value, (str, bool, int, float)):
            continue
        elif key in {"summary", "text", "title", "url", "sourceId", "sourceType", "region", "topic", "publishedAt"}:
            payload.pop(key, None)
    if actor:
        payload.setdefault("actor", actor)
    if "text" not in payload:
        payload["text"] = str(payload.get("title") or "")
    return await _news_xrpc("com.etzhayyim.apps.news.analyzeIntel", payload)


async def task_news_xrpc_publish_intel(input: dict | None = None) -> dict:
    """Call news.etzhayyim.com publishIntel from Zeebe BPMN."""
    payload = dict(input or {})
    if "url" not in payload and "sourceUrl" in payload:
        payload["url"] = payload["sourceUrl"]
    return await _news_xrpc("com.etzhayyim.apps.news.publishIntel", payload)


async def _serverless_image_gen(body: dict, timeout_sec: float, repo: str) -> dict:
    """RunPod Serverless /runsync flow: build workflow → submit → poll
    (if cold-start returns IN_QUEUE) → decode base64 → upload to PDS."""
    import base64 as _b64
    base = _COMFYUI_BASE.rstrip("/")
    url = f"{base}/runsync"
    # Body may already contain {input: {workflow}} OR be an OpenAI-shape
    # bag of params we need to translate.
    if isinstance(body.get("input"), dict) and isinstance(body["input"].get("workflow"), dict):
        payload_obj = body
    else:
        payload_obj = {"input": {"workflow": _build_txt2img_workflow(body)}}
    payload = json.dumps(payload_obj).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_COMFYUI_KEY}",
    }
    started = time.monotonic()

    def _post(u: str) -> tuple[int, dict]:
        req = _u_req.Request(u, data=payload, headers=headers, method="POST")
        try:
            with _u_req.urlopen(req, timeout=min(30.0, timeout_sec)) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except _u_err.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {"error": str(e)}
        except Exception as e:  # noqa: BLE001
            return -1, {"error": f"transport: {e}"}

    def _get(u: str) -> tuple[int, dict]:
        req = _u_req.Request(u, headers={"Authorization": f"Bearer {_COMFYUI_KEY}"}, method="GET")
        try:
            with _u_req.urlopen(req, timeout=30.0) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except _u_err.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {"error": str(e)}
        except Exception as e:  # noqa: BLE001
            return -1, {"error": f"transport: {e}"}

    status, data = await asyncio.to_thread(_post, url)
    images = _extract_serverless_images(data.get("output")) if isinstance(data, dict) else []

    # Cold start path — /runsync returned IN_QUEUE, poll /status until COMPLETED.
    if not images and isinstance(data, dict) and data.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
        job_id = data.get("id")
        if not job_id:
            return {"error": "no job id in runsync response", "status": status,
                    "latencyMs": int((time.monotonic() - started) * 1000)}
        status_url = f"{base}/status/{job_id}"
        deadline = started + min(timeout_sec, 300.0)
        while time.monotonic() < deadline:
            await asyncio.sleep(5)
            code, d = await asyncio.to_thread(_get, status_url)
            if not isinstance(d, dict):
                continue
            s = d.get("status")
            if s == "COMPLETED":
                images = _extract_serverless_images(d.get("output"))
                data = d
                break
            if s == "FAILED":
                return {"error": f"job failed: {json.dumps(d)[:500]}",
                        "latencyMs": int((time.monotonic() - started) * 1000)}

    latency_ms = int((time.monotonic() - started) * 1000)
    if not images:
        err = data.get("error") or data.get("output") or data
        return {"error": f"no images returned: {json.dumps(err)[:500]}",
                "status": status, "latencyMs": latency_ms}

    # Take the first image; base64-decode; upload to PDS as a blob.
    raw_b64 = images[0]
    # Strip data URL prefix if present
    if raw_b64.startswith("data:"):
        _, _, raw_b64 = raw_b64.partition(",")
    try:
        raw = _b64.b64decode(raw_b64)
    except Exception as e:  # noqa: BLE001
        return {"error": f"b64 decode: {e}", "latencyMs": latency_ms}

    upload_repo = repo or _COMFYUI_BLOB_REPO
    upload_url = f"{_PDS_BASE}/xrpc/com.atproto.repo.uploadBlob"
    upload_headers = {
        "Content-Type": "image/png",
        "x-kotoba-kotodama-verified": "true",
        "x-kotoba-kotodama-repo": upload_repo,
    }

    def _do_upload() -> tuple[int, dict | str]:
        req = _u_req.Request(upload_url, data=raw, headers=upload_headers, method="POST")
        try:
            with _u_req.urlopen(req, timeout=60.0) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except _u_err.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {"error": str(e)}
        except Exception as e:  # noqa: BLE001
            return -1, {"error": f"upload transport: {e}"}

    up_status, up_body = await asyncio.to_thread(_do_upload)
    blob_cid = ""
    meta: dict[str, Any] = {}
    if isinstance(up_body, dict):
        blob = up_body.get("blob") if isinstance(up_body.get("blob"), dict) else {}
        ref = blob.get("ref") if isinstance(blob.get("ref"), dict) else {}
        blob_cid = str(ref.get("$link") or "")
        meta = {"mimeType": blob.get("mimeType") or "image/png",
                "size": blob.get("size") or len(raw)}

    return {
        "status": 200,
        "blobCid": blob_cid,
        "meta": meta,
        "latencyMs": latency_ms,
        "uploadStatus": up_status,
        "route": "/v1/images/generations",
        "serverless": True,
        "delayTimeMs": data.get("delayTime") if isinstance(data, dict) else None,
        "executionTimeMs": data.get("executionTime") if isinstance(data, dict) else None,
    }


def _build_txt2img_workflow(body: dict) -> dict:
    """Translate OpenAI-shaped body → ComfyUI workflow graph.

    Supports the fields the animeka BPMN stages emit: prompt, model,
    size ("WxH"), steps, cfg_scale, seed, negative_prompt, sampler,
    scheduler, n.
    """
    size = str(body.get("size", "832x1216"))
    try:
        w_str, h_str = size.split("x", 1)
        w, h = int(w_str), int(h_str)
    except Exception:
        w, h = 832, 1216
    ckpt = str(body.get("model") or _COMFYUI_DEFAULT_CKPT)
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(body.get("seed", int(time.time() * 1000) & 0xFFFFFFFF)),
                "steps": int(body.get("steps", 20)),
                "cfg": float(body.get("cfg_scale", 6.0)),
                "sampler_name": str(body.get("sampler", "euler")),
                "scheduler": str(body.get("scheduler", "normal")),
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": int(body.get("n", 1))}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(body.get("prompt", "masterpiece, best quality")),
                         "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(body.get("negative_prompt", "lowres, bad anatomy, text, watermark")),
                         "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "bpmn"}},
    }


def _extract_serverless_images(output: dict | None) -> list[str]:
    """Pull base64 image strings out of RunPod Serverless /runsync output."""
    if not output:
        return []
    out: list[str] = []
    imgs = output.get("images")
    if isinstance(imgs, list):
        for img in imgs:
            if isinstance(img, dict) and isinstance(img.get("data"), str):
                out.append(img["data"])
    if isinstance(output.get("image"), str):
        out.append(output["image"])
    return out


async def _pd_color_local_media_call(route: str, body: dict, output_format: str) -> dict:
    """Persist pd-color media step manifests to IPFS and return their CIDs."""
    body = body if isinstance(body, dict) else {}
    kind_by_route = {
        "/v1/video/shot-segmentation": "pd-color-shot-map",
        "/v1/video/restore": "pd-color-restored-frames",
        "/v1/video/colorize": "pd-color-colorized-frames",
        "/v1/video/enhance-quality": "pd-color-enhanced-master",
        "/v1/video/encode-publication-package": "pd-color-publication-package",
        "/v1/audio/transcribe-and-align": "pd-color-timed-text",
        "/v1/audio/dub-localized-speech": "pd-color-dubbed-audio",
        "/v1/video/mux-localized-publication-package": "pd-color-localized-package",
    }
    kind = kind_by_route.get(route, "pd-color-media-step")
    target_languages = body.get("targetLanguages") if isinstance(body.get("targetLanguages"), list) else []
    cid = await _pd_color_add_json_manifest(
        kind,
        {
            "route": route,
            "outputFormat": output_format,
            "input": body,
        },
    )
    meta: dict[str, Any] = {"manifestKind": kind, "manifestCid": cid}

    if route == "/v1/video/shot-segmentation":
        meta["shotCount"] = 1
    elif route == "/v1/video/restore":
        meta.update({"frameCount": 0, "source": "manifest-only"})
    elif route == "/v1/video/colorize":
        meta.update({"model": "manifest-only", "palette": body.get("paletteReferenceCid") or "none"})
    elif route == "/v1/video/enhance-quality":
        meta.update({
            "qualityProfile": body.get("qualityProfile") or "archive-hq",
            "targetResolution": body.get("targetResolution") or "1080p",
            "grainPreservation": bool(body.get("grainPreservation", True)),
        })
    elif route == "/v1/video/encode-publication-package":
        poster_cid = await _pd_color_add_json_manifest(
            "pd-color-poster",
            {"sourceManifestCid": cid, "colorizedFramesCid": body.get("colorizedFramesCid")},
        )
        meta.update({"posterCid": poster_cid, "manifestCid": cid})
    elif route == "/v1/audio/transcribe-and-align":
        meta.update({"segmentCount": 0, "detectedLanguage": body.get("sourceLanguage") or "en"})
    elif route == "/v1/audio/dub-localized-speech":
        meta["generatedCount"] = len(target_languages)
    elif route == "/v1/video/mux-localized-publication-package":
        meta["packageCount"] = len(target_languages)

    return {"status": 200, "blobCid": cid, "meta": meta, "route": route}


def _pd_color_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def _pd_color_record_process_event(
    *,
    run_vertex_id: str,
    work_id: str = "",
    activity: str,
    task_type: str,
    lifecycle: str,
    status: str,
    started_at: float | None = None,
    artifact_cid: str = "",
    detail: dict | None = None,
) -> None:
    if os.environ.get("PDCOLOR_PROCESS_MINING_EVENTS", "1").lower() not in ("1", "true", "on", "yes"):
        return
    run_id = str(run_vertex_id or "").strip()
    if not run_id:
        return
    duration_ms = int((time.monotonic() - started_at) * 1000) if started_at is not None else None
    event_at = _pd_color_now()
    safe_activity = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", activity).strip("-")[:96] or "event"
    vertex_id = f"pdcolor:process-event:{run_id}:{safe_activity}:{int(time.time() * 1000)}"
    payload = {
        "vertex_id": vertex_id,
        "run_vertex_id": run_id,
        "work_id": work_id or None,
        "activity": activity,
        "task_type": task_type,
        "lifecycle": lifecycle,
        "status": status,
        "event_at": event_at,
        "duration_ms": duration_ms,
        "artifact_cid": artifact_cid or None,
        "detail_json": json.dumps(detail or {}, ensure_ascii=False, sort_keys=True, default=str),
        "owner_did": "did:web:pd-color.etzhayyim.com",
        "org_id": "did:web:pd-color.etzhayyim.com",
        "user_id": "did:web:pd-color.etzhayyim.com",
        "actor_id": "sys.bpmn.pd-color",
    }
    try:
        await task_generic_db_insert(
            table="vertex_pd_color_process_event",
            values=payload,
            onConflict="ignore",
        )
    except Exception as e:  # noqa: BLE001
        LOG.warning("pd-color process event write failed: %s", e)


def _pd_color_result_status(result: dict) -> str:
    if not isinstance(result, dict):
        return "unknown"
    if result.get("error"):
        return "failed"
    status = result.get("status")
    if isinstance(status, int) and status >= 400:
        return "failed"
    return "completed"


async def _pd_color_call_with_event(
    *,
    run_vertex_id: str,
    work_id: str = "",
    activity: str,
    task_type: str,
    call,
) -> dict:
    started = time.monotonic()
    try:
        result = await call()
    except Exception as e:  # noqa: BLE001
        await _pd_color_record_process_event(
            run_vertex_id=run_vertex_id,
            work_id=work_id,
            activity=activity,
            task_type=task_type,
            lifecycle="failed",
            status="failed",
            started_at=started,
            detail={"error": str(e)},
        )
        raise
    response = result.get("response") if isinstance(result.get("response"), dict) else {}
    await _pd_color_record_process_event(
        run_vertex_id=run_vertex_id,
        work_id=work_id,
        activity=activity,
        task_type=task_type,
        lifecycle="complete",
        status=_pd_color_result_status(result),
        started_at=started,
        artifact_cid=str(result.get("blobCid") or response.get("manifestCid") or ""),
        detail={"route": result.get("route"), "meta": result.get("meta"), "response": result.get("response")},
    )
    return result


async def task_generic_comfyui_call(route: str = "",
                                    body: dict | None = None,
                                    outputFormat: str = "auto",
                                    timeoutSec: float = 600.0,
                                    repo: str = "") -> dict:
    """ComfyUI gateway passthrough. POSTs JSON to comfyui.etzhayyim.com{route}
    and returns either the JSON payload (for chat/completions) or a
    content-addressed blob ref (for image/video/audio endpoints).

    Two upstream modes (auto-detected from COMFYUI_URL):

    - `gateway`: passthrough to a comfyui.etzhayyim.com-style OpenAI-compat
      adapter. Body is forwarded as-is. Binary responses become PDS
      blobs. (legacy ADR-0050 path)

    - `serverless`: when COMFYUI_URL points at a RunPod Serverless
      endpoint (e.g. https://api.runpod.ai/v2/<id>), and route is
      /v1/images/generations, the body is translated to a ComfyUI
      workflow graph, wrapped in {input:{workflow:...}}, POSTed to
      `{url}/runsync`, and the resulting base64 image is decoded and
      uploaded to the PDS as a blob. Returns {blobCid, meta, latencyMs}.

    `route` MUST start with "/v1/" — we deliberately don't expose the
    raw upstream to avoid being used as a generic HTTP proxy. Supported
    routes: /v1/images/{generations,edits}, /v1/videos/generations,
    /v1/audio/{speech,music}, /v1/chat/completions.

    For JSON responses, `bodyJson` is returned verbatim (chat path).
    """
    if not route:
        return {"error": "route required"}
    if not route.startswith("/v1/"):
        return {"error": "route must start with /v1/"}
    if route in _PD_COLOR_MEDIA_ROUTES and os.environ.get("PDCOLOR_LOCAL_MEDIA_MANIFESTS", "1").lower() in ("1", "true", "on", "yes"):
        return await _pd_color_local_media_call(route, body or {}, outputFormat)

    # _COMFYUI_KEY can be empty when talking to comfyui.etzhayyim.com (gateway
    # accepts x-kotoba-kotodama-verified internal-trust). RunPod direct URLs
    # require a real Bearer key — the upstream returns 401 if missing,
    # which surfaces in the BPMN audit.

    # Serverless path — RunPod /runsync with workflow wrapping.
    if _COMFYUI_SHAPE == "serverless" and route == "/v1/images/generations":
        return await _serverless_image_gen(body or {}, timeoutSec, repo)

    url = f"{_COMFYUI_BASE}{route}"
    # Accept steers the pod-side OpenAI adapter: image/* → raw PNG binary
    # (which we upload as a blob); otherwise JSON (chat-completions shape).
    accept = "image/*" if outputFormat == "binary" else "application/json"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_COMFYUI_KEY}",
        # Internal-trust shim — same pattern as shinshi_video._comfy_headers
        # (lines 60-71). When _COMFYUI_BASE is comfyui.etzhayyim.com the gateway
        # requireAuth short-circuits on this header (kind: "internal");
        # direct RunPod proxy URLs ignore it. Safe in both topologies.
        "x-kotoba-kotodama-verified": "true",
        # proxy.runpod.net is behind Cloudflare and returns 1010 to
        # python/urllib's default UA. Standard browser UA is benign
        # for comfyui.etzhayyim.com too (UA-indifferent).
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": accept,
    }
    payload = json.dumps(body or {}).encode("utf-8")
    started = time.monotonic()

    def _do_call() -> tuple[int, bytes, dict]:
        req = _u_req.Request(url, data=payload, headers=headers, method="POST")
        try:
            with _u_req.urlopen(req, timeout=timeoutSec) as resp:
                raw = resp.read()
                return resp.status, raw, dict(resp.headers)
        except _u_err.HTTPError as e:
            try:
                return e.code, e.read(4096), {}
            except Exception:
                return e.code, str(e).encode("utf-8"), {}
        except Exception as e:  # noqa: BLE001
            return -1, f"transport: {e}".encode("utf-8"), {}

    status, raw, hdrs = await asyncio.to_thread(_do_call)
    latency_ms = int((time.monotonic() - started) * 1000)
    content_type = (hdrs.get("Content-Type") or hdrs.get("content-type") or "").lower()
    want_json = outputFormat == "json" or "/chat/completions" in route or "json" in content_type

    if status < 0 or status >= 400:
        text = raw.decode("utf-8", errors="replace")[:800] if isinstance(raw, (bytes, bytearray)) else str(raw)
        return {"status": status, "error": text, "latencyMs": latency_ms, "route": route}

    if want_json:
        try:
            return {
                "status": status,
                "bodyJson": json.loads(raw.decode("utf-8")),
                "latencyMs": latency_ms,
                "route": route,
            }
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return {"status": status, "error": f"json parse: {e}",
                    "latencyMs": latency_ms, "route": route}

    # Binary response — upload to PDS as a content-addressed blob.
    # PDS upload endpoint expects raw binary + a mimeType. We derive the
    # mime from the upstream Content-Type, falling back to octet-stream.
    mime = content_type.split(";")[0].strip() or "application/octet-stream"
    upload_repo = repo or _COMFYUI_BLOB_REPO
    upload_url = f"{_PDS_BASE}/xrpc/com.atproto.repo.uploadBlob"
    upload_headers = {
        "Content-Type": mime,
        "x-kotoba-kotodama-verified": "true",
        "x-kotoba-kotodama-repo": upload_repo,
        # atproto.etzhayyim.com CF WAF rejects python/urllib's default UA
        # ahead of the handler (visible as 403 on an otherwise valid
        # internal-trust request). Same browser UA shim already used
        # for proxy.runpod.net (see llm.py) + the primitive's outbound
        # post above keeps the request pre-handler-acceptable.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    def _do_upload() -> tuple[int, dict | str]:
        req = _u_req.Request(upload_url, data=raw, headers=upload_headers, method="POST")
        try:
            with _u_req.urlopen(req, timeout=60.0) as resp:
                try:
                    return resp.status, json.loads(resp.read().decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return resp.status, {"error": "non-json uploadBlob response"}
        except _u_err.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            except Exception:
                return e.code, {"error": str(e)}
        except Exception as e:  # noqa: BLE001
            return -1, {"error": f"upload transport: {e}"}

    up_status, up_body = await asyncio.to_thread(_do_upload)
    blob_cid = ""
    meta: dict[str, Any] = {}
    if isinstance(up_body, dict):
        blob = up_body.get("blob") if isinstance(up_body.get("blob"), dict) else {}
        ref = blob.get("ref") if isinstance(blob.get("ref"), dict) else {}
        blob_cid = str(ref.get("$link") or "")
        meta = {
            "mimeType": blob.get("mimeType") or mime,
            "size": blob.get("size") or len(raw),
        }

    return {
        "status": status,
        "blobCid": blob_cid,
        "meta": meta,
        "latencyMs": latency_ms,
        "uploadStatus": up_status,
        "route": route,
    }


async def task_pd_color_video_segment_shots(sourceBlobCid: str = "",
                                            sourceIpfsCid: str = "",
                                            sourceIpfsUrl: str = "",
                                            workId: str = "",
                                            runVertexId: str = "") -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Segment shots",
        task_type="pdColor.video.segmentShots",
        call=lambda: task_generic_comfyui_call(
            route="/v1/video/shot-segmentation",
            body={
                "sourceBlobCid": sourceBlobCid,
                "sourceIpfsCid": sourceIpfsCid,
                "sourceIpfsUrl": sourceIpfsUrl,
                "workId": workId,
                "runVertexId": runVertexId,
            },
            outputFormat="json",
            timeoutSec=600,
        ),
    )


async def task_pd_color_video_restore_frames(sourceBlobCid: str = "",
                                             sourceIpfsCid: str = "",
                                             shotMapCid: str = "",
                                             workKind: str = "",
                                             qualityProfile: str = "archive-hq",
                                             targetResolution: str = "1080p",
                                             runVertexId: str = "",
                                             workId: str = "") -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Restore frames",
        task_type="pdColor.video.restoreFrames",
        call=lambda: task_generic_comfyui_call(
            route="/v1/video/restore",
            body={
                "sourceBlobCid": sourceBlobCid,
                "sourceIpfsCid": sourceIpfsCid,
                "shotMapCid": shotMapCid,
                "workKind": workKind,
                "qualityProfile": qualityProfile or "archive-hq",
                "targetResolution": targetResolution or "1080p",
                "stabilize": True,
                "degrain": True,
                "scratchRepair": True,
            },
            outputFormat="blob",
            timeoutSec=600,
        ),
    )


async def task_pd_color_video_colorize_frames(restoredFramesCid: str = "",
                                              shotMapCid: str = "",
                                              title: str = "",
                                              paletteReferenceCid: str = "",
                                              qualityProfile: str = "archive-hq",
                                              runVertexId: str = "",
                                              workId: str = "") -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Colorize frames",
        task_type="pdColor.video.colorizeFrames",
        call=lambda: task_generic_comfyui_call(
            route="/v1/video/colorize",
            body={
                "restoredFramesCid": restoredFramesCid,
                "shotMapCid": shotMapCid,
                "title": title,
                "paletteReferenceCid": paletteReferenceCid,
                "qualityProfile": qualityProfile or "archive-hq",
                "temporalConsistency": True,
            },
            outputFormat="blob",
            timeoutSec=600,
        ),
    )


async def task_pd_color_video_enhance_quality(colorizedFramesCid: str = "",
                                              masterVideoCid: str = "",
                                              shotMapCid: str = "",
                                              qualityProfile: str = "archive-hq",
                                              targetResolution: str = "1080p",
                                              grainPreservation: bool = True,
                                              runVertexId: str = "",
                                              workId: str = "") -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Enhance quality",
        task_type="pdColor.video.enhanceQuality",
        call=lambda: task_generic_comfyui_call(
            route="/v1/video/enhance-quality",
            body={
                "colorizedFramesCid": colorizedFramesCid,
                "masterVideoCid": masterVideoCid,
                "shotMapCid": shotMapCid,
                "qualityProfile": qualityProfile or "archive-hq",
                "targetResolution": targetResolution or "1080p",
                "grainPreservation": grainPreservation is not False,
            },
            outputFormat="blob",
            timeoutSec=600,
        ),
    )


async def task_pd_color_video_encode_package(colorizedFramesCid: str = "",
                                             sourceRecord: dict | None = None,
                                             rightsEvidenceCid: str = "",
                                             requestedLicense: str = "pd-mark",
                                             qualityProfile: str = "archive-hq",
                                             targetResolution: str = "1080p",
                                             runVertexId: str = "",
                                             workId: str = "") -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Encode package",
        task_type="pdColor.video.encodePackage",
        call=lambda: task_generic_comfyui_call(
            route="/v1/video/encode-publication-package",
            body={
                "colorizedFramesCid": colorizedFramesCid,
                "sourceRecord": sourceRecord or {},
                "rightsEvidenceCid": rightsEvidenceCid,
                "requestedLicense": requestedLicense,
                "qualityProfile": qualityProfile or "archive-hq",
                "targetResolution": targetResolution or "1080p",
            },
            outputFormat="blob",
            timeoutSec=600,
        ),
    )


async def task_pd_color_audio_extract_timed_text(masterVideoCid: str = "",
                                                 sourceLanguage: str = "",
                                                 workKind: str = "",
                                                 preserveIntertitles: bool = True,
                                                 runVertexId: str = "",
                                                 workId: str = "") -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Extract timed text",
        task_type="pdColor.audio.extractTimedText",
        call=lambda: task_generic_comfyui_call(
            route="/v1/audio/transcribe-and-align",
            body={
                "masterVideoCid": masterVideoCid,
                "sourceLanguage": sourceLanguage,
                "workKind": workKind,
                "preserveIntertitles": preserveIntertitles is not False,
            },
            outputFormat="json",
            timeoutSec=600,
        ),
    )


async def task_pd_color_localization_translate_subtitles(
    timedTextCid: str = "",
    sourceLanguage: str = "",
    detectedLanguage: str = "",
    targetLanguages: list | None = None,
    glossaryCid: str = "",
    title: str = "",
    workKind: str = "",
    rightsEvidenceCid: str = "",
    runVertexId: str = "",
    workId: str = "",
) -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Translate subtitles",
        task_type="pdColor.localization.translateSubtitles",
        call=lambda: task_generic_xrpc_invoke(
            nsid="com.etzhayyim.apps.i18n.translateBatch",
            payload={
                "project": "public-domain-colorization",
                "sourceLang": sourceLanguage or detectedLanguage or "en",
                "targetLangs": targetLanguages if isinstance(targetLanguages, list) else [],
                "sourceCid": timedTextCid,
                "contentKind": "timed-text",
                "glossaryCid": glossaryCid,
                "preserveTimestamps": True,
                "context": {
                    "title": title,
                    "workKind": workKind,
                    "rightsEvidenceCid": rightsEvidenceCid,
                },
            },
        ),
    )


async def task_pd_color_audio_generate_dubbed_audio(
    masterVideoCid: str = "",
    timedTextCid: str = "",
    subtitleManifestCid: str = "",
    targetLanguages: list | None = None,
    voicePolicy: str = "narration-neutral",
    voiceLipSync: bool = False,
    runVertexId: str = "",
    workId: str = "",
) -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Generate dubbed audio",
        task_type="pdColor.audio.generateDubbedAudio",
        call=lambda: task_generic_comfyui_call(
            route="/v1/audio/dub-localized-speech",
            body={
                "masterVideoCid": masterVideoCid,
                "timedTextCid": timedTextCid,
                "subtitleManifestCid": subtitleManifestCid,
                "targetLanguages": targetLanguages if isinstance(targetLanguages, list) else [],
                "voicePolicy": voicePolicy or "narration-neutral",
                "preserveOriginalAudio": True,
                "lipSync": voiceLipSync is True,
            },
            outputFormat="blob",
            timeoutSec=600,
        ),
    )


async def task_pd_color_video_mux_localized_packages(
    masterVideoCid: str = "",
    publicationManifestCid: str = "",
    subtitleManifestCid: str = "",
    dubbedAudioManifestCid: str = "",
    targetLanguages: list | None = None,
    runVertexId: str = "",
    workId: str = "",
) -> dict:
    return await _pd_color_call_with_event(
        run_vertex_id=runVertexId,
        work_id=workId,
        activity="Mux localized packages",
        task_type="pdColor.video.muxLocalizedPackages",
        call=lambda: task_generic_comfyui_call(
            route="/v1/video/mux-localized-publication-package",
            body={
                "masterVideoCid": masterVideoCid,
                "publicationManifestCid": publicationManifestCid,
                "subtitleManifestCid": subtitleManifestCid,
                "dubbedAudioManifestCid": dubbedAudioManifestCid,
                "targetLanguages": targetLanguages if isinstance(targetLanguages, list) else [],
            },
            outputFormat="blob",
            timeoutSec=600,
        ),
    )


def _parse_atom_feed(text: str) -> list[dict]:
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    feed_ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    ens = {"a": feed_ns} if feed_ns else {}
    prefix = "{feed_ns}" if feed_ns else ""
    entries = []
    for entry in root.findall(f"{{{feed_ns}}}entry" if feed_ns else "entry"):
        def _text(tag: str) -> str:
            el = entry.find(f"{{{feed_ns}}}{tag}" if feed_ns else tag)
            return (el.text or "").strip() if el is not None else ""
        link_el = entry.find(f"{{{feed_ns}}}link" if feed_ns else "link")
        link = (link_el.get("href") or "").strip() if link_el is not None else _text("link")
        entries.append({
            "id": _text("id"),
            "title": _text("title"),
            "link": link,
            "published": _text("published") or _text("updated"),
            "updated": _text("updated"),
            "summary": _text("summary") or _text("content"),
        })
    return entries


def _parse_oai_pmh(text: str) -> list[dict]:
    import xml.etree.ElementTree as ET  # noqa: PLC0415
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    ns_uri = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    dc_ns = "http://purl.org/dc/elements/1.1/"
    records = []
    list_records = root.find(f"{{{ns_uri}}}ListRecords" if ns_uri else "ListRecords")
    if list_records is None:
        return []
    for rec in list_records.findall(f"{{{ns_uri}}}record" if ns_uri else "record"):
        header = rec.find(f"{{{ns_uri}}}header" if ns_uri else "header")
        identifier, datestamp = "", ""
        if header is not None:
            id_el = header.find(f"{{{ns_uri}}}identifier" if ns_uri else "identifier")
            ds_el = header.find(f"{{{ns_uri}}}datestamp" if ns_uri else "datestamp")
            identifier = (id_el.text or "").strip() if id_el is not None else ""
            datestamp = (ds_el.text or "").strip() if ds_el is not None else ""
        meta = rec.find(f"{{{ns_uri}}}metadata" if ns_uri else "metadata")
        title, link = "", identifier
        if meta is not None:
            title_el = meta.find(f".//{{{dc_ns}}}title")
            link_el = meta.find(f".//{{{dc_ns}}}identifier")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if link_el is not None and (link_el.text or "").startswith("http"):
                link = (link_el.text or "").strip()
        records.append({"id": identifier, "link": link, "title": title, "published": datestamp})
    return records


async def task_generic_http_fetch(url: str = "", method: str = "GET",
                                  headers: dict | None = None,
                                  body: "str | dict | list | None" = "",
                                  contentType: str = "",
                                  parse: str = "",
                                  timeoutSec: float = 30.0) -> dict:
    """Generic outbound HTTP. JSON-decoded body if Content-Type
    suggests JSON; otherwise returned as `bodyText` (truncated 4KB)."""
    if not url:
        return {"error": "url required"}
    method = (method or "GET").upper()
    if not url.startswith(("http://", "https://")):
        return {"error": "url must include scheme"}
    # Browser-UA shim — dispatcher.etzhayyim.com / atproto.etzhayyim.com / proxy.runpod.net
    # all sit behind Cloudflare, which returns error 1010 (WAF) to
    # python/urllib's default UA. Default to browser UA; callers can
    # override via the `headers` input.
    merged_headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    if headers:
        merged_headers.update(headers)
    req = _u_req.Request(url, method=method, headers=merged_headers)
    if body:
        req.data = body.encode("utf-8") if isinstance(body, str) else body
    started = time.monotonic()

    def _do() -> tuple[int, str, dict]:
        # Bumped 4KB → 64KB so dispatcher /xrpc responses (which often
        # carry nested `variables` payloads ~1-10 KB) are not truncated
        # mid-JSON and parsed cleanly into bodyJson.
        try:
            with _u_req.urlopen(req, timeout=timeoutSec) as resp:
                raw = resp.read(65536)
                return resp.status, raw.decode("utf-8", errors="replace"), dict(resp.headers)
        except _u_err.HTTPError as e:
            try:
                return e.code, e.read(16384).decode("utf-8", errors="replace"), {}
            except Exception:
                return e.code, str(e), {}
        except Exception as e:  # noqa: BLE001
            return -1, f"transport: {e}", {}

    status, text, hdrs = await asyncio.to_thread(_do)
    out: dict[str, Any] = {
        "status": status,
        "latencyMs": int((time.monotonic() - started) * 1000),
        "headers": hdrs,
    }
    ct = (hdrs.get("Content-Type") or hdrs.get("content-type") or "").lower()
    if "json" in ct and text:
        try:
            out["bodyJson"] = json.loads(text)
        except json.JSONDecodeError:
            out["bodyText"] = text[:65536]
    else:
        out["bodyText"] = text[:65536]
    if parse == "atom":
        out["entries"] = _parse_atom_feed(text)
    elif parse == "oai-pmh":
        out["records"] = _parse_oai_pmh(text)
    return out


_IND_EFILING_ALLOWED_PROVIDERS = {
    "itr1": {"eri_type2_api", "authorized_eri"},
    "gstr3b": {"gsp_api", "authorized_gsp"},
    "epfo": {"authorized_epfo_integrator"},
    "esic": {"authorized_esic_integrator"},
}


def _env_key(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", s.upper()).strip("_")


def _record_ind_efiling_submission(row: dict[str, Any]) -> dict[str, Any]:
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT 1 FROM vertex_ind_efiling_submission WHERE vertex_id = %s LIMIT 1",
                (row["vertex_id"],),
            )
            if (_res[0] if _res else None):
                return {"ok": True, "existing": True}
            _res = client.q(
                "INSERT INTO vertex_ind_efiling_submission ("
                "vertex_id, _seq, created_date, sensitivity_ord, owner_did, "
                "jurisdiction, provider_key, provider_kind, source_vertex_id, "
                "idempotency_key, payload_hash, status, external_reference, "
                "authorization_ref, credential_ref, approved_by_did, "
                "adapter_status, adapter_response_json, created_at, org_id, user_id, actor_id"
                ") VALUES (%s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    row["vertex_id"],
                    row["_seq"],
                    row["created_date"],
                    row["sensitivity_ord"],
                    row.get("owner_did", ""),
                    row["jurisdiction"],
                    row["provider_key"],
                    row["provider_kind"],
                    row.get("source_vertex_id", ""),
                    row["idempotency_key"],
                    row["payload_hash"],
                    row["status"],
                    row.get("external_reference", ""),
                    row.get("authorization_ref", ""),
                    row.get("credential_ref", ""),
                    row.get("approved_by_did", ""),
                    row.get("adapter_status", ""),
                    json.dumps(row.get("adapter_response") or {}, sort_keys=True),
                    row["created_at"],
                    row.get("org_id", ""),
                    row.get("user_id", ""),
                    row.get("actor_id", ""),
                ),
            )
            _res = client.q(
                "SELECT 1 FROM vertex_ind_efiling_submission WHERE vertex_id = %s LIMIT 1",
                (row["vertex_id"],),
            )
            if not (_res[0] if _res else None):
                return {"ok": False, "error": "submission audit insert accepted but row is not query-visible"}
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        error = str(e)[:500]
        LOG.warning("ind.efiling.submit: audit insert failed: %s", error[:200])
        return {"ok": False, "error": error}


async def task_ind_efiling_submit(
    jurisdiction: str = "",
    providerKey: str = "",
    providerKind: str = "",
    sourceVertexId: str = "",
    payloadHash: str = "",
    payload: dict | None = None,
    dryRun: bool = True,
    authorizationRef: str = "",
    credentialRef: str = "",
    approvedByDid: str = "",
    idempotencyKey: str = "",
    ownerDid: str = "",
    orgId: str = "",
    userId: str = "",
    actorId: str = "",
    timeoutSec: float = 30.0,
) -> dict:
    """India government e-filing handoff.

    This worker never automates CAPTCHA/OTP/MFA or logs into a government
    portal directly. Live mode only calls an operator-configured HTTPS
    adapter for an authorized channel (ERI/GSP/integrator) and records the
    handoff in `vertex_ind_efiling_submission`.
    """
    jurisdiction_norm = (jurisdiction or "").strip().lower()
    provider_kind = (providerKind or "").strip().lower()
    provider_key = (providerKey or jurisdiction_norm).strip().lower()
    if jurisdiction_norm not in _IND_EFILING_ALLOWED_PROVIDERS:
        return {"ok": False, "status": "blocked", "error": f"unsupported jurisdiction: {jurisdiction!r}"}
    if provider_kind not in _IND_EFILING_ALLOWED_PROVIDERS[jurisdiction_norm]:
        return {
            "ok": False,
            "status": "blocked",
            "error": (
                f"providerKind {providerKind!r} is not allowed for {jurisdiction_norm}; "
                "use an authorized API/provider route, not portal scraping"
            ),
        }
    if not sourceVertexId:
        return {"ok": False, "status": "blocked", "error": "sourceVertexId required"}

    payload_obj = payload or {}
    payload_hash = payloadHash or hashlib.sha256(
        json.dumps(payload_obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    idem = idempotencyKey or f"{jurisdiction_norm}:{sourceVertexId}:{payload_hash}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    seq = int(time.time() * 1000)
    row_base = {
        "vertex_id": "at://did:web:ind-union.etzhayyim.com/com.etzhayyim.apps.ind.efiling.submission/"
        + hashlib.sha256(idem.encode("utf-8")).hexdigest()[:32],
        "_seq": seq,
        "created_date": time.strftime("%Y-%m-%d", time.gmtime()),
        "sensitivity_ord": 2,
        "owner_did": ownerDid or actorId or "did:web:ind-union.etzhayyim.com",
        "jurisdiction": jurisdiction_norm,
        "provider_key": provider_key,
        "provider_kind": provider_kind,
        "source_vertex_id": sourceVertexId,
        "idempotency_key": idem,
        "payload_hash": payload_hash,
        "authorization_ref": authorizationRef,
        "credential_ref": credentialRef,
        "approved_by_did": approvedByDid,
        "created_at": now,
        "org_id": orgId,
        "user_id": userId,
        "actor_id": actorId,
    }

    if dryRun or os.environ.get("IND_EFILING_LIVE_ENABLED", "0").lower() not in ("1", "true", "on", "yes"):
        row = {**row_base, "status": "dry_run", "adapter_status": "not_sent"}
        audit = _record_ind_efiling_submission(row)
        return {
            "ok": bool(audit.get("ok")),
            "status": "dry_run",
            "jurisdiction": jurisdiction_norm,
            "providerKey": provider_key,
            "payloadHash": payload_hash,
            "idempotencyKey": idem,
            "submissionVertexId": row["vertex_id"],
            "auditRecorded": bool(audit.get("ok")),
            "auditError": audit.get("error", ""),
        }

    missing = [
        name for name, value in (
            ("authorizationRef", authorizationRef),
            ("credentialRef", credentialRef),
            ("approvedByDid", approvedByDid),
        ) if not value
    ]
    if missing:
        row = {**row_base, "status": "blocked", "adapter_status": "missing_" + "_".join(missing)}
        audit = _record_ind_efiling_submission(row)
        return {
            "ok": False,
            "status": "blocked",
            "error": "missing " + ", ".join(missing),
            "auditRecorded": bool(audit.get("ok")),
            "auditError": audit.get("error", ""),
        }

    env_prefix = f"IND_EFILING_PROVIDER_{_env_key(provider_key)}"
    endpoint = os.environ.get(f"{env_prefix}_ENDPOINT", "")
    hmac_secret = os.environ.get(f"{env_prefix}_HMAC_SECRET", "")
    if not endpoint.startswith("https://"):
        row = {**row_base, "status": "blocked", "adapter_status": "provider_endpoint_not_configured"}
        audit = _record_ind_efiling_submission(row)
        return {
            "ok": False,
            "status": "blocked",
            "error": f"{env_prefix}_ENDPOINT must be an https URL",
            "auditRecorded": bool(audit.get("ok")),
            "auditError": audit.get("error", ""),
        }
    if not hmac_secret:
        row = {**row_base, "status": "blocked", "adapter_status": "provider_hmac_not_configured"}
        audit = _record_ind_efiling_submission(row)
        return {
            "ok": False,
            "status": "blocked",
            "error": f"{env_prefix}_HMAC_SECRET required",
            "auditRecorded": bool(audit.get("ok")),
            "auditError": audit.get("error", ""),
        }

    body_obj = {
        "jurisdiction": jurisdiction_norm,
        "providerKey": provider_key,
        "providerKind": provider_kind,
        "sourceVertexId": sourceVertexId,
        "payloadHash": payload_hash,
        "payload": payload_obj,
        "authorizationRef": authorizationRef,
        "credentialRef": credentialRef,
        "approvedByDid": approvedByDid,
        "idempotencyKey": idem,
    }
    body = json.dumps(body_obj, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(hmac_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    req = _u_req.Request(
        endpoint,
        method="POST",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": idem,
            "X-etzhayyim-Signature": "sha256=" + signature,
        },
    )
    started = time.monotonic()
    try:
        with _u_req.urlopen(req, timeout=max(1.0, min(float(timeoutSec or 30.0), 120.0))) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
            adapter_status = str(resp.status)
    except _u_err.HTTPError as e:
        raw = e.read(65536).decode("utf-8", errors="replace")
        adapter_status = str(e.code)
    except Exception as e:  # noqa: BLE001
        row = {**row_base, "status": "failed", "adapter_status": type(e).__name__, "adapter_response": {"error": str(e)}}
        audit = _record_ind_efiling_submission(row)
        return {
            "ok": False,
            "status": "failed",
            "error": str(e),
            "auditRecorded": bool(audit.get("ok")),
            "auditError": audit.get("error", ""),
            "latencyMs": int((time.monotonic() - started) * 1000),
        }

    try:
        adapter_response: dict[str, Any] = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        adapter_response = {"bodyText": raw[:4096]}
    status = str(adapter_response.get("status") or "").lower()
    if status in ("requires_user_action", "mfa_required", "otp_required"):
        final_status = "requires_user_action"
    elif adapter_status.startswith("2") and status not in ("failed", "blocked"):
        final_status = "submitted"
    else:
        final_status = "failed"
    row = {
        **row_base,
        "status": final_status,
        "external_reference": str(adapter_response.get("externalReference") or adapter_response.get("ackNumber") or adapter_response.get("arn") or ""),
        "adapter_status": adapter_status,
        "adapter_response": adapter_response,
    }
    audit = _record_ind_efiling_submission(row)
    return {
        "ok": final_status == "submitted" and bool(audit.get("ok")),
        "status": final_status,
        "adapterStatus": adapter_status,
        "externalReference": row["external_reference"],
        "submissionVertexId": row["vertex_id"],
        "auditRecorded": bool(audit.get("ok")),
        "auditError": audit.get("error", ""),
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


async def task_generic_audit_emit(
    actor: str = "",
    action: str = "",
    payload: dict | None = None,
    actor_did: str = "",
    event_type: str = "",
    eventType: str = "",
    attributes: dict | None = None,
) -> dict:
    """Append an audit row to vertex_repo_commit so BPMN-driven actions
    leave the same OCEL-compatible trail as the rest of the platform.
    Cheap, fire-and-forget.

    Schema (14 cols, all NOT NULL except vertex_id/created_at/record_cid):
      vertex_id, seq, repo, collection, rkey, action, rev, cid, prev,
      sig, value_json, ts_ms, created_at, record_cid

    `seq` post-ADR-0041 is just an ordering column (vertex_id is the
    content-addressed PK), so ts_ms doubles as a monotonic seq.
    """
    actor_value = actor or actor_did
    action_value = action or event_type or eventType
    payload_value = payload if payload is not None else (attributes or {})
    if not actor_value or not action_value:
        return {"error": "actor and action required"}
    ts_ms = int(time.time() * 1000)
    rkey = f"audit-{ts_ms}-{re.sub(r'[^a-zA-Z0-9]+', '-', action_value)[:32]}"
    vertex_id = f"{actor_value}:com.etzhayyim.bpmn.audit:{rkey}:create"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sql_text = (
        "INSERT INTO vertex_repo_commit ("
        "vertex_id, seq, repo, collection, rkey, action, "
        "rev, cid, prev, sig, value_json, ts_ms, created_at"
        ") SELECT %s, %s, %s, %s, %s, %s, '', '', '', '', %s, %s, %s "
        "WHERE NOT EXISTS (SELECT 1 FROM vertex_repo_commit WHERE vertex_id = %s)"
    )
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql_text, (
                vertex_id, ts_ms, actor_value, "com.etzhayyim.bpmn.audit", rkey, "create",
                json.dumps({"action": action_value, **payload_value}),
                ts_ms, created_at,
                vertex_id,
            ))
            return {"emitted": (len(_res) if isinstance(_res, list) else 1) > 0, "rkey": rkey, "vertexId": vertex_id}
    except Exception as e:  # noqa: BLE001
        return {"error": f"audit insert failed: {e}", "emitted": False}


async def task_kouza_sync_due_connections(maxConnections: int = 25,
                                          staleMinutes: int = 60,
                                          ownerDid: str = "",
                                          dryRun: bool = False) -> dict:
    """Resident kouza scheduler task.

    The MCP/UDF handler owns the DB mutation; the Zeebe worker wraps it so
    the same behavior is available from timer-start BPMN.
    """
    from kotodama.handlers.kouza import sync_due_connections_payload

    params = {
        "maxConnections": maxConnections,
        "staleMinutes": staleMinutes,
        "ownerDid": ownerDid,
        "dryRun": dryRun,
    }
    try:
        return await asyncio.to_thread(sync_due_connections_payload, params)
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"kouza.syncDueConnections failed: {e}",
            "connectionsScanned": 0,
            "syncRunsCreated": 0,
            "syncRunDids": [],
        }


async def task_ingest_run_mark_completed(
    runId: str = "",
    status: str = "completed",
    recordsRead: int | None = None,
    recordsWritten: int | None = None,
    recordsSkipped: int | None = None,
    errorCount: int | None = None,
    lastError: str = "",
) -> dict:
    """Mark a durable ingest run terminal from BPMN.

    Source-specific ingest tasks will pass real counters later. The control
    BPMN uses this to close the run lifecycle after health/audit succeeds.
    """
    if not runId:
        return {"ok": False, "error": "runId required"}
    terminal = status if status in {"completed", "failed", "degraded"} else "completed"
    try:
        from kotodama.ingest.core import mark_run_finished

        mark_run_finished(
            runId,
            status=terminal,
            records_read=recordsRead,
            records_written=recordsWritten,
            records_skipped=recordsSkipped,
            error_count=errorCount,
            last_error=lastError or None,
            output={"markedBy": "ingest.run.markCompleted"},
        )
        return {"ok": True, "runId": runId, "status": terminal}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "runId": runId, "error": f"markCompleted failed: {e}"}


async def task_blockchain_head_ingest(
    runId: str = "",
    sourceId: str = "",
    inputJson: str = "",
    maxBlocks: int | None = None,
) -> dict:
    """Read blockchain node RPC and write deterministic head-delta rows."""
    if not runId:
        return {"ok": False, "error": "runId required"}
    if not sourceId:
        return {"ok": False, "error": "sourceId required"}
    try:
        from kotodama.ingest.blockchain import ingest_head_delta

        LOG.info("blockchain.head.ingest start runId=%s sourceId=%s maxBlocks=%s", runId, sourceId, maxBlocks)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_head_delta,
            run_id=runId,
            source_id=sourceId,
            input_json=inputJson or "{}",
            max_blocks=maxBlocks,
        )
        LOG.info(
            "blockchain.head.ingest done runId=%s sourceId=%s ok=%s rowsWritten=%s latencyMs=%s wallMs=%s",
            runId,
            sourceId,
            result.get("ok"),
            result.get("rowsWritten"),
            result.get("latencyMs"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("blockchain.head.ingest failed runId=%s sourceId=%s", runId, sourceId)
        return {"ok": False, "runId": runId, "sourceId": sourceId, "error": f"blockchain.head.ingest failed: {e}"}


async def task_business_profit_settle_open_adnetwork(
    settlementId: str = "",
    windowHours: int = 24,
    publisherDid: str = "__all__",
    publisherSharePct: float = 70.0,
    minGrossRevenueUsd: float = 0.0,
    submitReceipt: bool = True,
) -> dict:
    """Settle open-adnetwork revenue into a profit ledger row.

    This is intentionally one business task instead of a large FEEL-heavy BPMN:
    the BPMN owns cadence and orchestration, while this worker owns the
    idempotent business transaction and optional private-chain anchoring.
    """
    try:
        hours = max(1, min(int(windowHours or 24), 24 * 31))
    except (TypeError, ValueError):
        hours = 24
    try:
        share_pct = max(0.0, min(float(publisherSharePct), 100.0))
    except (TypeError, ValueError):
        share_pct = 70.0
    try:
        min_gross = max(0.0, float(minGrossRevenueUsd or 0.0))
    except (TypeError, ValueError):
        min_gross = 0.0

    finished_ms = int(time.time() * 1000)
    started_ms = finished_ms - hours * 60 * 60 * 1000
    publisher_filter = (publisherDid or "__all__").strip() or "__all__"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    where_publisher = "" if publisher_filter == "__all__" else "AND au.publisher_did = %s"
    params: list[Any] = [started_ms, finished_ms]
    if publisher_filter != "__all__":
        params.append(publisher_filter)

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""
                SELECT
                  COALESCE(SUM(i.cpm_usd) / 1000.0, 0.0) AS gross_revenue_usd,
                  COUNT(*) AS impressions,
                  COALESCE(COUNT(DISTINCT au.publisher_did), 0) AS publisher_count
                FROM vertex_open_adnetwork_impression i
                JOIN vertex_open_adnetwork_ad_unit au ON au.unit_id = i.unit_id
                WHERE i.ts_ms >= %s
                  AND i.ts_ms < %s
                  {where_publisher}
                """,
                tuple(params),
            )
            row = (_res[0] if _res else None) or (0.0, 0, 0)
    except Exception as e:  # noqa: BLE001
        LOG.exception("business.profit.settleOpenAdnetwork aggregate failed")
        return {"ok": False, "error": f"aggregate failed: {e}", "settled": False}

    gross_revenue = float(row[0] or 0.0)
    impressions = int(row[1] or 0)
    publisher_count = int(row[2] or 0)
    publisher_profit = gross_revenue * share_pct / 100.0
    platform_profit = gross_revenue - publisher_profit
    settlement_id = (
        settlementId.strip()
        if settlementId.strip()
        else f"open-adnetwork-profit-{publisher_filter}-{started_ms}-{finished_ms}"
    )
    vertex_id = (
        "at://did:web:yoro.etzhayyim.com/com.etzhayyim.apps.business.profitSettlement/"
        + hashlib.sha256(settlement_id.encode("utf-8")).hexdigest()[:32]
    )

    status = "settled" if gross_revenue >= min_gross and impressions > 0 else "below-threshold"
    receipt: dict[str, Any] = {"submitted": False, "reason": "not-requested"}
    output_payload = {
        "settlementId": settlement_id,
        "publisherDid": publisher_filter,
        "windowStartMs": started_ms,
        "windowEndMs": finished_ms,
        "impressions": impressions,
        "publisherCount": publisher_count,
        "grossRevenueUsd": gross_revenue,
        "publisherProfitUsd": publisher_profit,
        "platformProfitUsd": platform_profit,
        "status": status,
    }

    if submitReceipt and status == "settled":
        input_hash = _sha256_json({
            "publisherDid": publisher_filter,
            "windowStartMs": started_ms,
            "windowEndMs": finished_ms,
            "publisherSharePct": share_pct,
        })
        output_hash = _sha256_json(output_payload)
        receipt = await _maybe_record_runtime_receipt(
            job_id=_bytes32_hex(settlement_id, field="settlementId"),
            actor_did=_bytes32_hex("did:web:yoro.etzhayyim.com", field="actorDid"),
            artifact_id=_bytes32_hex("business.profit.settleOpenAdnetwork.v1", field="artifactId"),
            input_hash=input_hash,
            output_hash=output_hash,
            trace_hash=_sha256_json({"task": "business.profit.settleOpenAdnetwork", "createdAt": created_at}),
            operator_did=_bytes32_hex("did:web:yoro.etzhayyim.com:actor:business", field="operatorDid"),
            started_at=started_ms,
            finished_at=finished_ms,
        )

    tx_hash = ""
    for line in str(receipt.get("stdout") or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] == "transactionHash" and parts[1].startswith("0x"):
            tx_hash = parts[1].strip()
            break

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_open_adnetwork_profit_settlement (
                  vertex_id, settlement_id, publisher_did, window_start_ms, window_end_ms,
                  impressions, publisher_count, gross_revenue_usd, publisher_share_pct,
                  publisher_profit_usd, platform_profit_usd, currency, chain_id,
                  chain_receipt_submitted, chain_receipt_tx, chain_receipt_reason,
                  status, created_at, sensitivity_ord, org_id, user_id, actor_id,
                  actor_did, org_did
                )
                SELECT
                  %s::varchar, %s::varchar, %s::varchar, %s::bigint, %s::bigint,
                  %s::bigint, %s::integer, %s::double precision, %s::double precision,
                  %s::double precision, %s::double precision, 'USD', 260425,
                  %s::boolean, %s::varchar, %s::varchar,
                  %s::varchar, %s::varchar, 0, 'did:web:yoro.etzhayyim.com',
                  'did:web:yoro.etzhayyim.com', 'sys.bpmn.business-profit',
                  'did:web:yoro.etzhayyim.com', 'did:web:yoro.etzhayyim.com'
                WHERE NOT EXISTS (
                  SELECT 1 FROM vertex_open_adnetwork_profit_settlement
                  WHERE settlement_id = %s::varchar
                )
                """,
                (
                    vertex_id,
                    settlement_id,
                    publisher_filter,
                    started_ms,
                    finished_ms,
                    impressions,
                    publisher_count,
                    gross_revenue,
                    share_pct,
                    publisher_profit,
                    platform_profit,
                    bool(receipt.get("submitted")),
                    tx_hash,
                    str(receipt.get("reason") or ""),
                    status,
                    created_at,
                    settlement_id,
                ),
            )
            inserted = (len(_res) if isinstance(_res, list) else 1) if (len(_res) if isinstance(_res, list) else 1) is not None else 0
    except Exception as e:  # noqa: BLE001
        LOG.exception("business.profit.settleOpenAdnetwork insert failed settlementId=%s", settlement_id)
        return {**output_payload, "ok": False, "error": f"insert failed: {e}", "receipt": receipt}

    return {
        **output_payload,
        "ok": True,
        "settled": status == "settled",
        "inserted": inserted,
        "vertexId": vertex_id,
        "chainReceiptSubmitted": bool(receipt.get("submitted")),
        "chainReceiptTx": tx_hash,
        "chainReceipt": receipt,
    }


# --- netintel ingest tasks (Zeebe migration from collector CF Worker) ---

async def task_netintel_dns_delta(
    targetTier: str = "shadow",
    batchSize: int = 200,
    runId: str = "",
) -> dict:
    """Re-probe stale domains in vertex_dns_observation via RDAP + Cloudflare DoH."""
    try:
        from kotodama.ingest.netintel_dns import ingest_dns_delta

        LOG.info("netintel.dns.delta start targetTier=%s batchSize=%s", targetTier, batchSize)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_dns_delta,
            run_id=runId,
            target_tier=targetTier,
            batch_size=int(batchSize),
        )
        LOG.info(
            "netintel.dns.delta done ok=%s domainsRead=%s rowsWritten=%s wallMs=%s",
            result.get("ok"), result.get("domainsRead"), result.get("rowsWritten"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("netintel.dns.delta failed")
        return {"ok": False, "error": f"netintel.dns.delta failed: {e}"}


async def task_netintel_ip_enrich(
    targetTier: str = "shadow",
    batchSize: int = 500,
    runId: str = "",
) -> dict:
    """Enrich stale IPs in vertex_ip_address via ipinfo.io GeoIP."""
    try:
        from kotodama.ingest.ip_enrich import ingest_ip_enrich

        LOG.info("netintel.ip.enrich start targetTier=%s batchSize=%s", targetTier, batchSize)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_ip_enrich,
            run_id=runId,
            target_tier=targetTier,
            batch_size=int(batchSize),
        )
        LOG.info(
            "netintel.ip.enrich done ok=%s ipsRead=%s rowsWritten=%s wallMs=%s",
            result.get("ok"), result.get("ipsRead"), result.get("rowsWritten"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("netintel.ip.enrich failed")
        return {"ok": False, "error": f"netintel.ip.enrich failed: {e}"}


async def task_netintel_whois_delta(
    targetTier: str = "shadow",
    batchSize: int = 200,
    runId: str = "",
) -> dict:
    """Snapshot WHOIS/RDAP data for stale domains into vertex_whois_record."""
    try:
        from kotodama.ingest.whois_rdap import ingest_whois_delta

        LOG.info("netintel.whois.delta start targetTier=%s batchSize=%s", targetTier, batchSize)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_whois_delta,
            run_id=runId,
            target_tier=targetTier,
            batch_size=int(batchSize),
        )
        LOG.info(
            "netintel.whois.delta done ok=%s domainsRead=%s rowsWritten=%s wallMs=%s",
            result.get("ok"), result.get("domainsRead"), result.get("rowsWritten"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("netintel.whois.delta failed")
        return {"ok": False, "error": f"netintel.whois.delta failed: {e}"}


async def task_netintel_scan_banner(
    targetTier: str = "shadow",
    batchSize: int = 100,
    runId: str = "",
) -> dict:
    """Port scan + banner grab stale IPs via external SCAN_PROXY_URL."""
    try:
        from kotodama.ingest.scan_banner import ingest_scan_banner

        LOG.info("netintel.scan.banner start targetTier=%s batchSize=%s", targetTier, batchSize)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_scan_banner,
            run_id=runId,
            target_tier=targetTier,
            batch_size=int(batchSize),
        )
        LOG.info(
            "netintel.scan.banner done ok=%s ipsScanned=%s rowsWritten=%s wallMs=%s",
            result.get("ok"), result.get("ipsScanned"), result.get("rowsWritten"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("netintel.scan.banner failed")
        return {"ok": False, "error": f"netintel.scan.banner failed: {e}"}


async def task_netintel_fingerprint_delta(
    targetTier: str = "shadow",
    batchSize: int = 100,
    runId: str = "",
) -> dict:
    """TLS/HTTP fingerprint stale hosts (port 443 + 80) via external SCAN_PROXY_URL."""
    try:
        from kotodama.ingest.fingerprint import ingest_fingerprint_delta

        LOG.info("netintel.fingerprint.delta start targetTier=%s batchSize=%s", targetTier, batchSize)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_fingerprint_delta,
            run_id=runId,
            target_tier=targetTier,
            batch_size=int(batchSize),
        )
        LOG.info(
            "netintel.fingerprint.delta done ok=%s hostsProbed=%s rowsWritten=%s wallMs=%s",
            result.get("ok"), result.get("hostsProbed"), result.get("rowsWritten"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("netintel.fingerprint.delta failed")
        return {"ok": False, "error": f"netintel.fingerprint.delta failed: {e}"}


async def task_bluesky_ingest_actor(
    actor: str = "",
    appview: str = "https://public.api.bsky.app",
    nanoid: str = "bsky1ngs",
) -> dict:
    """Ingest one public Bluesky actor via AppView.

    This is the Zeebe/Python replacement for the former CF Worker
    `/xrpc/com.etzhayyim.apps.bluesky.ingestActor` business logic.
    """
    try:
        from kotodama.ingest.bluesky import ingest_actor

        LOG.info("bluesky.ingest.actor start actor=%s appview=%s", actor, appview)
        started = time.monotonic()
        result = await asyncio.to_thread(
            ingest_actor,
            actor=actor,
            appview=appview,
            nanoid=nanoid,
        )
        LOG.info(
            "bluesky.ingest.actor done actor=%s ok=%s ingested=%s tombstoned=%s wallMs=%s",
            actor,
            result.get("ok"),
            result.get("ingested"),
            result.get("tombstoned"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("bluesky.ingest.actor failed actor=%s", actor)
        return {"ok": False, "actor": actor, "error": f"bluesky.ingest.actor failed: {e}"}


async def task_bluesky_refresh_stalest(
    batchSize: int = 10,
    appview: str = "https://public.api.bsky.app",
    nanoid: str = "bsky1ngs",
) -> dict:
    """Refresh the stalest tracked Bluesky actors.

    BPMN timer replacement for the former CF Worker `scheduled()` cron.
    """
    try:
        from kotodama.ingest.bluesky import refresh_stalest

        LOG.info("bluesky.ingest.refreshStalest start batchSize=%s appview=%s", batchSize, appview)
        started = time.monotonic()
        result = await asyncio.to_thread(
            refresh_stalest,
            batch_size=int(batchSize or 10),
            appview=appview,
            nanoid=nanoid,
        )
        LOG.info(
            "bluesky.ingest.refreshStalest done ok=%s actorsRead=%s ingested=%s tombstoned=%s wallMs=%s",
            result.get("ok"),
            result.get("actorsRead"),
            result.get("ingested"),
            result.get("tombstoned"),
            int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:  # noqa: BLE001
        LOG.exception("bluesky.ingest.refreshStalest failed")
        return {"ok": False, "error": f"bluesky.ingest.refreshStalest failed: {e}"}


async def _briefing_persist(result: dict) -> dict:
    if not result.get("ok"):
        return result
    records = result.pop("records", []) or []
    posts = result.pop("posts", []) or []
    persisted: list[dict[str, Any]] = []
    for item in records:
        collection = item.get("collection")
        record = item.get("record") or {}
        persisted.append(await task_generic_pds_dispatch(
            type="com.atproto.repo.createRecord",
            payload={"collection": collection, "recordJson": json.dumps(record, ensure_ascii=False)},
            callerDid="did:web:briefing.etzhayyim.com",
        ))
    for post in posts:
        persisted.append(await task_generic_pds_dispatch(
            type="app.bsky.feed.post",
            payload={"text": str(post.get("text") or "")},
            callerDid="did:web:briefing.etzhayyim.com",
        ))
    result["persisted"] = persisted
    return result


async def task_briefing_create_agenda(**kwargs: Any) -> dict:
    from kotodama.ingest.briefing import create_agenda
    return await _briefing_persist(await asyncio.to_thread(create_agenda, **kwargs))


async def task_briefing_save_transcript(**kwargs: Any) -> dict:
    from kotodama.ingest.briefing import save_transcript
    return await _briefing_persist(await asyncio.to_thread(save_transcript, **kwargs))


async def task_briefing_extract_action_items(**kwargs: Any) -> dict:
    from kotodama.ingest.briefing import extract_action_items
    return await _briefing_persist(await asyncio.to_thread(extract_action_items, **kwargs))


async def task_briefing_generate_summary(**kwargs: Any) -> dict:
    from kotodama.ingest.briefing import generate_summary
    return await _briefing_persist(await asyncio.to_thread(generate_summary, **kwargs))


async def task_briefing_record_speaker_turn(**kwargs: Any) -> dict:
    from kotodama.ingest.briefing import record_speaker_turn
    return await _briefing_persist(await asyncio.to_thread(record_speaker_turn, **kwargs))


async def task_briefing_record_decision(**kwargs: Any) -> dict:
    from kotodama.ingest.briefing import record_decision
    return await _briefing_persist(await asyncio.to_thread(record_decision, **kwargs))


async def task_arb_scout_quotes(assetClass: str = "") -> dict:
    try:
        from kotodama.ingest.arbitrage import scout_quotes

        return await asyncio.to_thread(scout_quotes, asset_class=assetClass)
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.scoutQuotes failed")
        return {"ok": False, "error": f"arb.scoutQuotes failed: {e}"}


async def task_arb_ingest_quote(**kwargs: Any) -> dict:
    try:
        from kotodama.ingest.arbitrage import ingest_quote

        return await asyncio.to_thread(ingest_quote, kwargs)
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.ingestQuote failed")
        return {"ok": False, "error": f"arb.ingestQuote failed: {e}"}


async def task_arb_detect_spread(assetClass: str = "", minSpreadBps: float = 20) -> dict:
    try:
        from kotodama.ingest.arbitrage import detect_spread

        return await asyncio.to_thread(detect_spread, asset_class=assetClass, min_spread_bps=float(minSpreadBps or 20))
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.detectSpread failed")
        return {"ok": False, "error": f"arb.detectSpread failed: {e}"}


async def task_arb_propose_trade(**kwargs: Any) -> dict:
    try:
        from kotodama.ingest.arbitrage import propose_trade

        return await asyncio.to_thread(propose_trade, kwargs)
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.proposeTrade failed")
        return {"ok": False, "error": f"arb.proposeTrade failed: {e}"}


async def task_arb_score_proposal(proposalId: str = "", model: str = "heuristic-v1") -> dict:
    try:
        from kotodama.ingest.arbitrage import score_proposal

        return await asyncio.to_thread(score_proposal, proposal_id=proposalId, model=model)
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.scoreProposal failed")
        return {"ok": False, "error": f"arb.scoreProposal failed: {e}"}


async def task_arb_publish_proposal(
    proposalId: str = "",
    mentionCohort: str = "trader.etzhayyim.com",
    disclaimer: str = "Educational signal. Not advice. No execution.",
) -> dict:
    try:
        from kotodama.ingest.arbitrage import publish_proposal

        return await asyncio.to_thread(
            publish_proposal,
            proposal_id=proposalId,
            mention_cohort=mentionCohort,
            disclaimer=disclaimer,
        )
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.publishProposal failed")
        return {"ok": False, "error": f"arb.publishProposal failed: {e}"}


async def task_arb_list_proposals(
    limit: int = 50,
    offset: int = 0,
    minEdgeBps: float = 20,
    assetClass: str = "",
) -> dict:
    try:
        from kotodama.ingest.arbitrage import list_proposals

        return await asyncio.to_thread(
            list_proposals,
            limit=int(limit or 50),
            offset=int(offset or 0),
            min_edge_bps=float(minEdgeBps or 20),
            asset_class=assetClass,
        )
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.listProposals failed")
        return {"ok": False, "error": f"arb.listProposals failed: {e}"}


async def task_arb_get_proposal(proposalId: str = "") -> dict:
    try:
        from kotodama.ingest.arbitrage import get_proposal

        return await asyncio.to_thread(get_proposal, proposal_id=proposalId)
    except Exception as e:  # noqa: BLE001
        LOG.exception("arb.getProposal failed")
        return {"ok": False, "error": f"arb.getProposal failed: {e}"}


async def _arms_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import arms

    fn = getattr(arms, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


async def task_arms_register_firearm(**kwargs: Any) -> dict:
    return await _arms_call("register_firearm", kwargs)


async def task_arms_authenticate_holder(**kwargs: Any) -> dict:
    return await _arms_call("authenticate_holder", kwargs)


async def task_arms_verify_auth_challenge(**kwargs: Any) -> dict:
    return await _arms_call("verify_auth_challenge", kwargs)


async def task_arms_issue_permit(**kwargs: Any) -> dict:
    return await _arms_call("issue_permit", kwargs)


async def task_arms_transfer_custody(**kwargs: Any) -> dict:
    return await _arms_call("transfer_custody", kwargs)


async def task_arms_check_out_firearm(**kwargs: Any) -> dict:
    return await _arms_call("check_out_firearm", kwargs)


async def task_arms_check_in_firearm(**kwargs: Any) -> dict:
    return await _arms_call("check_in_firearm", kwargs)


async def task_arms_report_incident(**kwargs: Any) -> dict:
    return await _arms_call("report_incident", kwargs)


async def task_arms_get_firearm(**kwargs: Any) -> dict:
    return await _arms_call("get_firearm", kwargs)


async def task_arms_list_firearms(**kwargs: Any) -> dict:
    return await _arms_call("list_firearms", kwargs)


async def task_arms_list_permits(**kwargs: Any) -> dict:
    return await _arms_call("list_permits", kwargs)


async def task_arms_get_audit_log(**kwargs: Any) -> dict:
    return await _arms_call("get_audit_log", kwargs)


async def _collector_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import collector

    fn = getattr(collector, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


async def task_collector_collect_netintel_dns(**kwargs: Any) -> dict:
    return await _collector_call("collect_netintel_dns", kwargs)


async def task_collector_collect_blockchain_btc(**kwargs: Any) -> dict:
    return await _collector_call("collect_blockchain_btc", kwargs)


async def task_collector_collect_blockchain_eth(**kwargs: Any) -> dict:
    return await _collector_call("collect_blockchain_eth", kwargs)


async def task_collector_collect_common_crawl(**kwargs: Any) -> dict:
    return await _collector_call("collect_common_crawl", kwargs)


async def task_collector_collect_archive(**kwargs: Any) -> dict:
    return await _collector_call("collect_archive", kwargs)


async def task_collector_ingest_scan_result(**kwargs: Any) -> dict:
    return await _collector_call("ingest_scan_result", kwargs)


async def task_collector_trigger_run(**kwargs: Any) -> dict:
    return await _collector_call("trigger_run", kwargs)


async def task_collector_get_dashboard(**kwargs: Any) -> dict:
    return await _collector_call("get_dashboard", kwargs)


async def task_collector_list_jobs(**kwargs: Any) -> dict:
    return await _collector_call("list_jobs", kwargs)


async def _calendar_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import calendar

    fn = getattr(calendar, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


async def task_calendar_create_event(**kwargs: Any) -> dict:
    return await _calendar_call("create_event", kwargs)


async def task_calendar_update_event(**kwargs: Any) -> dict:
    return await _calendar_call("update_event", kwargs)


async def task_calendar_delete_event(**kwargs: Any) -> dict:
    return await _calendar_call("delete_event", kwargs)


async def task_calendar_list_events(**kwargs: Any) -> dict:
    return await _calendar_call("list_events", kwargs)


async def task_calendar_get_event(**kwargs: Any) -> dict:
    return await _calendar_call("get_event", kwargs)


async def task_calendar_create_recurring(**kwargs: Any) -> dict:
    return await _calendar_call("create_recurring", kwargs)


async def task_calendar_rsvp(**kwargs: Any) -> dict:
    return await _calendar_call("rsvp", kwargs)


async def task_calendar_list_invitations(**kwargs: Any) -> dict:
    return await _calendar_call("list_invitations", kwargs)


async def task_calendar_connect_account(**kwargs: Any) -> dict:
    return await _calendar_call("connect_account", kwargs)


async def task_calendar_oauth_callback(**kwargs: Any) -> dict:
    return await _calendar_call("oauth_callback", kwargs)


async def task_calendar_sync_from_google(**kwargs: Any) -> dict:
    return await _calendar_call("sync_from_google", kwargs)


async def task_calendar_cron_tick(**kwargs: Any) -> dict:
    return await _calendar_call("cron_tick", kwargs)


async def _animeka_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import animeka

    fn = getattr(animeka, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


async def task_animeka_create_work(**kwargs: Any) -> dict:
    return await _animeka_call("create_work", kwargs)


async def task_animeka_list_works(**kwargs: Any) -> dict:
    return await _animeka_call("list_works", kwargs)


async def task_animeka_add_episode(**kwargs: Any) -> dict:
    return await _animeka_call("add_episode", kwargs)


async def task_animeka_list_episodes(**kwargs: Any) -> dict:
    return await _animeka_call("list_episodes", kwargs)


async def task_animeka_publish_episode_app(**kwargs: Any) -> dict:
    return await _animeka_call("publish_episode", kwargs)


async def task_animeka_add_cut(**kwargs: Any) -> dict:
    return await _animeka_call("add_cut", kwargs)


async def task_animeka_list_cuts(**kwargs: Any) -> dict:
    return await _animeka_call("list_cuts", kwargs)


async def task_animeka_get_cut(**kwargs: Any) -> dict:
    return await _animeka_call("get_cut", kwargs)


async def task_animeka_update_cut_stage(**kwargs: Any) -> dict:
    return await _animeka_call("update_cut_stage", kwargs)


async def task_animeka_submit_retake(**kwargs: Any) -> dict:
    return await _animeka_call("submit_retake", kwargs)


async def task_animeka_resolve_retake(**kwargs: Any) -> dict:
    return await _animeka_call("resolve_retake", kwargs)


async def task_animeka_list_retakes(**kwargs: Any) -> dict:
    return await _animeka_call("list_retakes", kwargs)


async def task_animeka_health(**kwargs: Any) -> dict:
    return await _animeka_call("health", kwargs)


async def _gworkspace_lite_call(app: str, fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import gworkspace_lite

    fn = getattr(gworkspace_lite, fn_name)
    return await asyncio.to_thread(fn, app, **kwargs)


def _make_gworkspace_lite_task(app: str, fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _gworkspace_lite_call(app, fn_name, kwargs)

    _task.__name__ = f"task_{app}_{fn_name}"
    return _task


async def _gworkspace_service_call(app: str, fn_name: str, kwargs: dict[str, Any]) -> dict:
    import importlib

    mod = importlib.import_module(f"kotodama.ingest.{app}")
    fn = getattr(mod, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_gworkspace_service_task(app: str, fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _gworkspace_service_call(app, fn_name, kwargs)

    _task.__name__ = f"task_{app}_{fn_name}"
    return _task


async def _gmail_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import gmail

    fn = getattr(gmail, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_gmail_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _gmail_call(fn_name, kwargs)

    _task.__name__ = f"task_gmail_{fn_name}"
    return _task


async def _outlook_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import outlook

    fn = getattr(outlook, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_outlook_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _outlook_call(fn_name, kwargs)

    _task.__name__ = f"task_outlook_{fn_name}"
    return _task


async def _credits_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import credits

    fn = getattr(credits, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_credits_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _credits_call(fn_name, kwargs)

    _task.__name__ = f"task_credits_{fn_name}"
    return _task


async def _mailer_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import mailer

    fn = getattr(mailer, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_mailer_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _mailer_call(fn_name, kwargs)

    _task.__name__ = f"task_mailer_{fn_name}"
    return _task


async def _stripe_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import stripe

    fn = getattr(stripe, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_stripe_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _stripe_call(fn_name, kwargs)

    _task.__name__ = f"task_stripe_{fn_name}"
    return _task


async def _ads_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import ads

    fn = getattr(ads, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_ads_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _ads_call(fn_name, kwargs)

    _task.__name__ = f"task_ads_{fn_name}"
    return _task


async def _shiharai_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import shiharai

    fn = getattr(shiharai, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_shiharai_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _shiharai_call(fn_name, kwargs)

    _task.__name__ = f"task_shiharai_{fn_name}"
    return _task


async def _kouza_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import kouza

    fn = getattr(kouza, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_kouza_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _kouza_call(fn_name, kwargs)

    _task.__name__ = f"task_kouza_{fn_name}"
    return _task


async def _kaikei_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import kaikei

    fn = getattr(kaikei, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_kaikei_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _kaikei_call(fn_name, kwargs)

    _task.__name__ = f"task_kaikei_{fn_name}"
    return _task


async def _moneyforward_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import moneyforward_ops

    fn = getattr(moneyforward_ops, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_moneyforward_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _moneyforward_call(fn_name, kwargs)

    _task.__name__ = f"task_moneyforward_{fn_name}"
    return _task


async def _ka_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import ka

    fn = getattr(ka, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_ka_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _ka_call(fn_name, kwargs)

    _task.__name__ = f"task_ka_{fn_name}"
    return _task


async def _kg_curator_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import kg_curator

    fn = getattr(kg_curator, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_kg_curator_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _kg_curator_call(fn_name, kwargs)

    _task.__name__ = f"task_kg_curator_{fn_name}"
    return _task


async def _demining_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import demining

    fn = getattr(demining, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_demining_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _demining_call(fn_name, kwargs)

    _task.__name__ = f"task_demining_{fn_name}"
    return _task


async def _dns_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import dns

    fn = getattr(dns, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_dns_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _dns_call(fn_name, kwargs)

    _task.__name__ = f"task_dns_{fn_name}"
    return _task


async def _kami_ketsu_gorilla_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import kami_ketsu_gorilla

    fn = getattr(kami_ketsu_gorilla, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_kami_ketsu_gorilla_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _kami_ketsu_gorilla_call(fn_name, kwargs)

    _task.__name__ = f"task_kami_ketsu_gorilla_{fn_name}"
    return _task


async def _real_estate_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import real_estate

    fn = getattr(real_estate, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_real_estate_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _real_estate_call(fn_name, kwargs)

    _task.__name__ = f"task_real_estate_{fn_name}"
    return _task


async def _mold_allergy_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import mold_allergy

    fn = getattr(mold_allergy, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_mold_allergy_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _mold_allergy_call(fn_name, kwargs)

    _task.__name__ = f"task_mold_allergy_{fn_name}"
    return _task


async def _kami_eng_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import kami_eng

    fn = getattr(kami_eng, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_kami_eng_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _kami_eng_call(fn_name, kwargs)

    _task.__name__ = f"task_kami_eng_{fn_name}"
    return _task


async def _i18n_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import i18n

    fn = getattr(i18n, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_i18n_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _i18n_call(fn_name, kwargs)

    _task.__name__ = f"task_i18n_{fn_name}"
    return _task


async def _baminiku_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import baminiku

    fn = getattr(baminiku, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_baminiku_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _baminiku_call(fn_name, kwargs)

    _task.__name__ = f"task_baminiku_{fn_name}"
    return _task


async def _game_play_uploader_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import game_play_uploader

    fn = getattr(game_play_uploader, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_game_play_uploader_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _game_play_uploader_call(fn_name, kwargs)

    _task.__name__ = f"task_game_play_uploader_{fn_name}"
    return _task


async def _apps_directory_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import apps_directory

    fn = getattr(apps_directory, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_apps_directory_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _apps_directory_call(fn_name, kwargs)

    _task.__name__ = f"task_apps_directory_{fn_name}"
    return _task


async def _nist_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import nist

    fn = getattr(nist, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_nist_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _nist_call(fn_name, kwargs)

    _task.__name__ = f"task_nist_{fn_name}"
    return _task


async def _vehicle_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import vehicle

    fn = getattr(vehicle, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_vehicle_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _vehicle_call(fn_name, kwargs)

    _task.__name__ = f"task_vehicle_{fn_name}"
    return _task


async def _vin_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import vin

    fn = getattr(vin, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_vin_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _vin_call(fn_name, kwargs)

    _task.__name__ = f"task_vin_{fn_name}"
    return _task


async def _vessel_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import vessel

    fn = getattr(vessel, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_vessel_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _vessel_call(fn_name, kwargs)

    _task.__name__ = f"task_vessel_{fn_name}"
    return _task


async def _port_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import port

    fn = getattr(port, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_port_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _port_call(fn_name, kwargs)

    _task.__name__ = f"task_port_{fn_name}"
    return _task


async def _maps_collection_call(fn_name: str, kwargs: dict[str, Any]) -> dict:
    from kotodama.ingest import maps_collection

    fn = getattr(maps_collection, fn_name)
    return await asyncio.to_thread(fn, **kwargs)


def _make_maps_collection_task(fn_name: str):
    async def _task(**kwargs: Any) -> dict:
        return await _maps_collection_call(fn_name, kwargs)

    _task.__name__ = f"task_maps_collection_{fn_name}"
    return _task


async def task_rw_health_probe(
    selectTimeoutSec: int = 5,
    minComputeAgeSec: int = 900,
    slowdownWindowSec: int = 60,
    slowdownMax: int = 10,
) -> dict:
    """3-point RisingWave health probe (deps.toml [[conventions]]
    rw-health-gate-before-ingest). Used by BPMN bulk-ingest processes
    as the first service task; on degraded result the process pivots
    to pre-fetch-only mode and skips the db.insert leg.

    Shells out to the canonical implementation at
    ``70-tools/scripts/ingest/rw-health-gate.sh`` so behaviour stays
    identical between scripted and BPMN invocations. The script's
    exit code maps to: 0 healthy, 1 degraded, 2 probe-failed.
    """
    script = os.environ.get(
        "RW_HEALTH_GATE_SCRIPT",
        "/app/70-tools/scripts/ingest/rw-health-gate.sh",
    )
    env = {
        **os.environ,
        "SELECT1_TIMEOUT_SEC":   str(selectTimeoutSec),
        "MIN_COMPUTE_AGE_SEC":   str(minComputeAgeSec),
        "SLOWDOWN_WINDOW_SEC":   str(slowdownWindowSec),
        "SLOWDOWN_MAX":          str(slowdownMax),
        "VERBOSE":               "1",
    }
    try:
        proc = await asyncio.create_subprocess_exec(
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except (FileNotFoundError, PermissionError) as e:
        return {"healthy": False, "reason": f"probe-unavailable: {e}", "exitCode": 2}
    except asyncio.TimeoutError:
        return {"healthy": False, "reason": "probe-timeout", "exitCode": 2}
    tail = (stdout or b"").decode(errors="replace").strip().splitlines()[-1:] or [""]
    return {
        "healthy":   proc.returncode == 0,
        "exitCode":  proc.returncode,
        "reason":    tail[-1],
        "verbose":   (stderr or b"").decode(errors="replace"),
    }


def _normalize_source_ids(source_ids: Any) -> list[str]:
    if isinstance(source_ids, list):
        vals = source_ids
    elif isinstance(source_ids, str):
        vals = [part.strip() for part in source_ids.split(",")]
    else:
        vals = []
    return [str(v).strip() for v in vals if str(v).strip()]


async def task_gyosei_source_link(
    caseId: str = "",
    sourceIds: Any = None,
    relation: str = "review-reference",
    note: str = "",
    memoId: str = "",
) -> dict:
    """Persist source snapshot references for gyosei review / precedent memo steps."""
    if not caseId:
        return {"error": "caseId required", "linked": 0}
    normalized = _normalize_source_ids(sourceIds)
    if not normalized:
        return {"linked": 0, "caseId": caseId, "relation": relation, "sourceIds": []}

    owner_did = "did:web:jpn-state.etzhayyim.com:gyosei"
    use_precedent_edge = bool(memoId) or relation.startswith("precedent-")
    resolved_memo_id = memoId or f"memo:{caseId}"
    linked = 0

    try:
        if True:
            client = get_kotoba_client()
            for source_id in normalized:
                source_vertex_id = f"gyosei-source:{source_id}"
                if use_precedent_edge:
                    edge_id = f"{owner_did}:edge_gyosei_precedent_source:{resolved_memo_id}:{source_id}:{relation}"
                    _res = client.q(
                        """
                        INSERT INTO edge_gyosei_precedent_source (
                          edge_id, owner_did, memo_id, case_id, source_vertex_id, relation, note, created_at
                        ) SELECT %s, %s, %s, %s, %s, %s, %s, NOW()
                        WHERE EXISTS (
                          SELECT 1 FROM vertex_gyosei_source_blob WHERE vertex_id = %s
                        )
                        AND NOT EXISTS (
                          SELECT 1 FROM edge_gyosei_precedent_source WHERE edge_id = %s
                        )
                        """,
                        (
                            edge_id, owner_did, resolved_memo_id, caseId, source_vertex_id, relation, note,
                            source_vertex_id, edge_id,
                        ),
                    )
                else:
                    edge_id = f"{owner_did}:edge_gyosei_case_source:{caseId}:{source_id}:{relation}"
                    _res = client.q(
                        """
                        INSERT INTO edge_gyosei_case_source (
                          edge_id, owner_did, case_id, source_vertex_id, relation, note, created_at
                        ) SELECT %s, %s, %s, %s, %s, %s, NOW()
                        WHERE EXISTS (
                          SELECT 1 FROM vertex_gyosei_source_blob WHERE vertex_id = %s
                        )
                        AND NOT EXISTS (
                          SELECT 1 FROM edge_gyosei_case_source WHERE edge_id = %s
                        )
                        """,
                        (
                            edge_id, owner_did, caseId, source_vertex_id, relation, note,
                            source_vertex_id, edge_id,
                        ),
                    )
                linked += (len(_res) if isinstance(_res, list) else 1) or 0
    except Exception as e:  # noqa: BLE001
        return {
            "error": f"gyosei source link failed: {e}",
            "linked": linked,
            "caseId": caseId,
            "relation": relation,
            "memoId": resolved_memo_id if use_precedent_edge else "",
        }

    return {
        "linked": linked,
        "caseId": caseId,
        "relation": relation,
        "memoId": resolved_memo_id if use_precedent_edge else "",
        "sourceIds": normalized,
    }


async def task_shinka_tick(actor: str = "") -> dict:
    """Call the existing `shinka_tick_actor(text)` SQL UDF for one actor.

    Kept as a dedicated task rather than `generic.db.*` because
    `generic.db.select` restricts the table name to the
    `(vertex|edge|mv)_*` allowlist; a raw UDF call falls outside that
    policy on purpose.

    The UDF returns a JSON-encoded dict with the full tick result
    (mood, axes, actions, write receipts, compose draft). We surface
    the useful top-level fields so Zeebe callers can branch on them.
    """
    if not actor:
        return {"error": "actor required"}
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q("SELECT shinka_tick_actor(%s)", (actor,))
            row = (_res[0] if _res else None)
    except Exception as e:  # noqa: BLE001
        return {"error": f"shinka_tick_actor failed: {e}", "actor": actor}

    raw = row[0] if row else None
    tick: dict[str, Any]
    if isinstance(raw, str):
        try:
            tick = json.loads(raw)
        except json.JSONDecodeError:
            tick = {"raw": raw}
    elif isinstance(raw, dict):
        tick = raw
    else:
        tick = {"raw": repr(raw)}

    return {
        "actor":            tick.get("actor_did") or actor,
        "mood":             tick.get("mood"),
        "actions":          tick.get("actions") or [],
        "heartbeatWritten": bool(tick.get("heartbeat_written")),
        "evolutionWritten": bool(tick.get("evolution_written")),
        "knowledgeWritten": bool(tick.get("knowledge_written")),
        "tickMs":           tick.get("tick_ms"),
    }


# ─── generic.tls.probe — TLS cert + handshake probe ─────────────────────
#
# Replaces `openssl s_client` one-shots used by the yabai phishing-infra
# tracking scripts. BPMN authors pass `{host, port?}` (or `{url}`) and get
# back the handshake status, peer certificate summary, and derived
# anomaly flags (self-signed, expired, short-lived, SAN mismatch). The
# primitive does NOT fetch HTTP — it only completes the TLS handshake and
# harvests `socket.getpeercert()`. If the caller needs content, use
# `generic.http.fetch` after this.
#
# Timeouts are bounded by `timeoutSec` (default 8s). ssl + socket are
# stdlib so no image dep changes.

import socket as _socket  # noqa: E402
import ssl as _ssl  # noqa: E402


def _parse_tls_time(raw: str | None) -> str | None:
    """openssl prints cert times as e.g. 'Jun  1 12:00:00 2026 GMT'.
    Convert to ISO 8601 for downstream FEEL `date and time()` parsing."""
    if not raw:
        return None
    try:
        dt_obj = time.strptime(raw, "%b %d %H:%M:%S %Y %Z")
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", dt_obj)
    except ValueError:
        return raw  # fall back to raw so BPMN can still audit it


def _cert_san_dns(cert: dict) -> list[str]:
    out: list[str] = []
    for typ, val in cert.get("subjectAltName", []) or []:
        if typ == "DNS" and isinstance(val, str):
            out.append(val.lower())
    return out


def _cert_cn(cert: dict) -> str | None:
    for rdn in cert.get("subject", []) or []:
        for key, val in rdn or []:
            if key == "commonName" and isinstance(val, str):
                return val
    return None


def _cert_issuer_cn(cert: dict) -> str | None:
    for rdn in cert.get("issuer", []) or []:
        for key, val in rdn or []:
            if key == "commonName" and isinstance(val, str):
                return val
    return None


def _host_matches_san(host: str, san_dns: list[str]) -> bool:
    h = (host or "").lower()
    if not h:
        return False
    for entry in san_dns:
        if entry == h:
            return True
        if entry.startswith("*.") and h.endswith(entry[1:]) and h.count(".") >= entry.count("."):
            return True
    return False


def _decode_cert_bin(cert_bin: bytes | None) -> dict:
    """`ssl.getpeercert()` returns {} when verify_mode=CERT_NONE. We need
    the parsed dict regardless of trust, so dump the DER to a temp PEM
    and decode via `ssl._ssl._test_decode_cert` (the same path the stdlib
    uses internally when verify_mode is not CERT_NONE)."""
    if not cert_bin:
        return {}
    import tempfile
    try:
        pem = _ssl.DER_cert_to_PEM_cert(cert_bin)
    except Exception:  # noqa: BLE001
        return {}
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pem", delete=False, encoding="ascii",
        ) as f:
            f.write(pem)
            tmp_path = f.name
        try:
            return _ssl._ssl._test_decode_cert(tmp_path)  # type: ignore[attr-defined]
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        return {}


def _tls_probe_sync(host: str, port: int, timeout: float, server_name: str) -> dict[str, Any]:
    ctx = _ssl.create_default_context()
    # Self-signed / expired certs are a *signal* the caller wants to see
    # (phishing infra frequently ships broken TLS). Don't fail the handshake
    # on those — capture the cert details + anomaly flags instead.
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE

    started = time.monotonic()
    sni = server_name or host
    with _socket.create_connection((host, port), timeout=timeout) as raw:
        with ctx.wrap_socket(raw, server_hostname=sni) as tls:
            cert_bin = tls.getpeercert(binary_form=True)
            cipher = tls.cipher()
            version = tls.version()
    # With verify_mode=CERT_NONE, getpeercert() returns {} — decode the
    # raw DER ourselves so the caller still gets subject/issuer/SAN.
    cert = _decode_cert_bin(cert_bin)

    not_before = _parse_tls_time((cert or {}).get("notBefore"))
    not_after = _parse_tls_time((cert or {}).get("notAfter"))
    san = _cert_san_dns(cert or {})
    subject_cn = _cert_cn(cert or {})
    issuer_cn = _cert_issuer_cn(cert or {})

    anomalies: list[str] = []
    # self-signed: subject == issuer (string-compare the full RDN tuple).
    if cert and cert.get("subject") == cert.get("issuer"):
        anomalies.append("self-signed")
    now_epoch = int(time.time())
    if not_after and not_after != (cert or {}).get("notAfter"):
        # notAfter was parseable → check expiry via struct_time
        try:
            na = time.strptime((cert or {}).get("notAfter", ""), "%b %d %H:%M:%S %Y %Z")
            if time.mktime(na) < now_epoch:
                anomalies.append("expired")
        except ValueError:
            pass
    if not_before and not_after:
        try:
            nb = time.strptime((cert or {}).get("notBefore", ""), "%b %d %H:%M:%S %Y %Z")
            na = time.strptime((cert or {}).get("notAfter", ""), "%b %d %H:%M:%S %Y %Z")
            lifetime_days = (time.mktime(na) - time.mktime(nb)) / 86400
            if 0 < lifetime_days < 30:
                anomalies.append("short-lived")
        except ValueError:
            pass
    if san and not _host_matches_san(host, san):
        anomalies.append("san-mismatch")

    return {
        "ok": True,
        "host": host,
        "port": port,
        "tlsVersion": version,
        "cipher": {"name": cipher[0], "protocol": cipher[1], "bits": cipher[2]} if cipher else None,
        "subjectCn": subject_cn,
        "issuerCn": issuer_cn,
        "san": san,
        "notBefore": not_before,
        "notAfter": not_after,
        "certSizeBytes": len(cert_bin) if cert_bin else 0,
        "anomalies": anomalies,
        "latencyMs": int((time.monotonic() - started) * 1000),
    }


async def task_generic_tls_probe(host: str = "", port: int = 443,
                                 timeoutSec: float = 8.0,
                                 serverName: str = "") -> dict:
    """TLS handshake + peer-cert probe.

    Input:
      host        required — hostname or IP to connect to
      port        default 443
      timeoutSec  default 8s (max: clamp to 30)
      serverName  optional SNI override (default: host)

    Output on success:
      ok, host, port, tlsVersion, cipher{name,protocol,bits},
      subjectCn, issuerCn, san[], notBefore, notAfter, certSizeBytes,
      anomalies[] (self-signed / expired / short-lived / san-mismatch),
      latencyMs

    On transport failure: {ok: false, error: "...", host, port, latencyMs}.
    Never throws — BPMN callers can audit the failure shape.
    """
    if not host:
        return {"ok": False, "error": "host required"}
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"invalid port: {port!r}"}
    if port_int < 1 or port_int > 65535:
        return {"ok": False, "error": f"port out of range: {port_int}"}
    try:
        timeout = float(timeoutSec)
    except (TypeError, ValueError):
        timeout = 8.0
    timeout = max(1.0, min(timeout, 30.0))

    started = time.monotonic()
    try:
        return await asyncio.to_thread(
            _tls_probe_sync, host, port_int, timeout, serverName or host,
        )
    except _socket.timeout:
        return {"ok": False, "error": "timeout", "host": host, "port": port_int,
                "latencyMs": int((time.monotonic() - started) * 1000)}
    except (_ssl.SSLError, _socket.gaierror, ConnectionError, OSError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "host": host,
                "port": port_int,
                "latencyMs": int((time.monotonic() - started) * 1000)}


# ─── Worker bootstrap ─────────────────────────────────────────────────────

# Liveness heartbeat — touched on each successful gRPC topology() ping by
# the watchdog. K8s liveness probe checks mtime: if older than 60s the
# pod is killed and restarted with a fresh gRPC channel. Caches a stale
# LangServer channel can return UsageError("Channel is closed") indefinitely
# without auto-reconnect, silently parking BPMN tokens (observed
# 2026-04-25 during animeka call-activity rollout).
_HEARTBEAT_PATH = Path(os.environ.get("LANGSERVER_WORKER_HEARTBEAT", "/tmp/langserver_worker_alive"))


async def _watchdog(channel: Any, stop_event: asyncio.Event) -> None:
    """Touch the LangServer liveness file while the pod process is healthy."""
    del channel
    PING_INTERVAL_S = 30.0
    try:
        _HEARTBEAT_PATH.touch()
    except OSError as e:
        LOG.warning("watchdog: heartbeat touch failed: %s", e)
    while not stop_event.is_set():
        try:
            _HEARTBEAT_PATH.touch()
        except OSError as e:
            LOG.warning("watchdog: heartbeat touch failed: %s", e)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=PING_INTERVAL_S)
        except asyncio.TimeoutError:
            pass


# Job-activation rate monitor — polls Zeebe broker's Spring Boot
# Actuator metrics. Logs ALERT when the broker stops handing out jobs
# while pending jobs exist. Complements the gRPC channel watchdog: the
# watchdog catches client-side connection death; this monitor catches
# broker-side scheduling stalls (back-pressure, partition issues, etc.).
_LANGSERVER_METRICS_URL = os.environ.get(
    "LANGSERVER_METRICS_URL", "http://agentgateway-mcp.mitama-udf.svc.cluster.local:8080/actuator/prometheus",
)
_ACTIVATION_METRIC_RE = re.compile(
    r'^zeebe_job_events_total\{[^}]*action="activated"[^}]*\}\s+(\d+(?:\.\d+)?)',
    re.MULTILINE,
)


async def _activation_monitor(stop_event: asyncio.Event) -> None:
    """Poll Zeebe broker /actuator/prometheus every 60s. Sum
    `zeebe_job_events_total{action="activated"}` across job_type labels
    and emit ERROR-level log if the counter does not advance for 5 min.

    All worker replicas poll independently (cheap, broker-side metric is
    identical from each viewpoint); deduplication happens at the log
    shipper. Hostname is included so per-pod views remain attributable.
    """
    POLL_INTERVAL_S = 60.0
    ALERT_THRESHOLD_S = 300.0
    POLL_TIMEOUT_S = 8.0
    hostname = os.environ.get("HOSTNAME", "unknown")
    last_value: float | None = None
    last_change_ts: float = time.time()
    while not stop_event.is_set():
        try:
            body = await asyncio.to_thread(
                lambda: urllib.request.urlopen(_LANGSERVER_METRICS_URL, timeout=POLL_TIMEOUT_S).read().decode(),
            )
            total = sum(float(m.group(1)) for m in _ACTIVATION_METRIC_RE.finditer(body))
            now = time.time()
            if last_value is None:
                last_value = total
                last_change_ts = now
                LOG.info("activation_monitor: baseline activated_total=%.0f host=%s", total, hostname)
            elif total > last_value:
                LOG.info(
                    "activation_monitor: +%.0f activations in %.0fs (total=%.0f host=%s)",
                    total - last_value, now - last_change_ts, total, hostname,
                )
                last_value = total
                last_change_ts = now
            else:
                stale_for = now - last_change_ts
                if stale_for >= ALERT_THRESHOLD_S:
                    LOG.error(
                        "ALERT activation_monitor: zero activations for %.0fs (total=%.0f host=%s) — broker→worker job dispatch stalled",
                        stale_for, total, hostname,
                    )
        except Exception as e:  # noqa: BLE001
            LOG.warning("activation_monitor: poll failed: %s", str(e)[:200])
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_S)
        except asyncio.TimeoutError:
            pass


# ─── legal.corpus.embedText — local CPU embedding via sentence-transformers ──
#
# Uses BAAI/bge-m3 (multilingual, 1024-dim) loaded lazily on first call.
# Model weights ~2.3 GB; first-call download is gated by a 120s task timeout.
# Runs on CPU — no GPU required. Replaces the CF Workers AI generic.http.fetch
# path (which requires com.cloudflare.api.account.ai scope we don't have).

_legal_embed_model: "Any | None" = None
_legal_embed_lock: "asyncio.Lock | None" = None


async def task_legal_corpus_embed_text(text: str = "") -> dict:
    global _legal_embed_model, _legal_embed_lock
    if _legal_embed_lock is None:
        _legal_embed_lock = asyncio.Lock()
    async with _legal_embed_lock:
        if _legal_embed_model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]
            _legal_embed_model = await asyncio.to_thread(
                SentenceTransformer, "BAAI/bge-m3"
            )
    if not text:
        return {"embedding": [], "dim": 0}
    # Truncate to 2048 chars (~512 tokens) so CPU encoding stays under ~15s
    # and the Zeebe gRPC channel survives the encoding window.
    text_truncated = text[:2048]
    embedding = await asyncio.to_thread(
        lambda: _legal_embed_model.encode(  # type: ignore[union-attr]
            text_truncated, normalize_embeddings=True
        ).tolist()
    )
    return {"embedding": embedding, "dim": len(embedding)}


async def task_legal_corpus_search_document(
    queryText: str = "",
    jurisdiction: str = "",
    documentType: str = "",
    languageCode: str = "",
    decidedAfter: str = "",
    decidedBefore: str = "",
    limit: int = 10,
) -> dict:
    """Vector similarity search over vertex_legal_corpus_document.

    Embeds queryText with bge-m3 then runs cosine similarity query.
    Vector is formatted inline as a string literal to avoid RisingWave's
    rejection of ::vector(1024) in psycopg parameterized statements.
    """
    if not queryText:
        return {"hits": [], "hitCount": 0, "error": "queryText required"}

    # Embed query — reuse the already-loaded model.
    global _legal_embed_model, _legal_embed_lock
    if _legal_embed_lock is None:
        _legal_embed_lock = asyncio.Lock()
    async with _legal_embed_lock:
        if _legal_embed_model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]
            _legal_embed_model = await asyncio.to_thread(
                SentenceTransformer, "BAAI/bge-m3"
            )
    embedding: list[float] = await asyncio.to_thread(
        lambda: _legal_embed_model.encode(  # type: ignore[union-attr]
            queryText[:2048], normalize_embeddings=True
        ).tolist()
    )

    # Format vector inline — RisingWave rejects ::vector in parameterized stmts.
    vec_literal = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
    limit_i = max(1, min(int(limit), 100))

    # Build optional WHERE clauses (all additive).
    where_parts = ["embedding_vec IS NOT NULL"]
    if jurisdiction:
        where_parts.append(f"jurisdiction = '{jurisdiction.replace(chr(39), '')}'")
    if documentType:
        where_parts.append(f"document_type = '{documentType.replace(chr(39), '')}'")
    if languageCode:
        where_parts.append(f"language_code = '{languageCode.replace(chr(39), '')}'")
    if decidedAfter:
        where_parts.append(f"decided_at >= '{decidedAfter.replace(chr(39), '')}'")
    if decidedBefore:
        where_parts.append(f"decided_at < '{decidedBefore.replace(chr(39), '')}'")
    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT vertex_id, canonical_uri, title, court, jurisdiction,
               document_type, language_code, source_id,
               1 - (embedding_vec <=> '{vec_literal}'::vector(1024)) AS score
        FROM vertex_legal_corpus_document
        WHERE {where_sql}
        ORDER BY embedding_vec <=> '{vec_literal}'::vector(1024)
        LIMIT {limit_i}
    """
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql)
            col_names = [d[0] for d in []] if [] else []
            rows = _res or []
        import datetime
        from decimal import Decimal

        def _coerce(v: object) -> object:
            if isinstance(v, (datetime.date, datetime.datetime)):
                return v.isoformat()
            if isinstance(v, Decimal):
                return float(v)
            return v

        hits = [{k: _coerce(v) for k, v in dict(zip(col_names, r)).items()} for r in rows]
        return {"hits": hits, "hitCount": len(hits)}
    except Exception as e:  # noqa: BLE001
        return {"hits": [], "hitCount": 0, "error": f"search failed: {e}"}


async def task_legal_corpus_fetch_body_text(
    canonicalUri: str = "",
    sourceId: str = "",
    maxChars: int = 50000,
) -> dict:
    """Fetch plain-text body for a legal document from its canonical URI.

    EUR-Lex CELLAR: GET <cellar_uri> Accept: application/xhtml+xml → strip tags.
    CourtListener:  plain_text is in the opinion JSON — not fetched here.
    Returns {"bodyText": str, "chars": int} or {"error": ..., "bodyText": ""}."""
    if not canonicalUri:
        return {"error": "canonicalUri required", "bodyText": ""}

    def _fetch_eur_lex_xhtml(uri: str) -> tuple[int, str]:
        import urllib.request as _ureq
        import urllib.error as _uerr
        import html.parser as _hp
        import re as _re

        https_uri = uri.replace("http://", "https://", 1) if uri.startswith("http://") else uri
        req = _ureq.Request(
            https_uri,
            headers={
                "Accept": "application/xhtml+xml",
                "Accept-Language": "en",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; etzhayyim-legal-corpus/1.0; "
                    "+https://legal-corpus.etzhayyim.com)"
                ),
            },
        )
        try:
            with _ureq.urlopen(req, timeout=30) as resp:
                raw = resp.read(maxChars * 4)
                xhtml = raw.decode("utf-8", errors="replace")
        except _uerr.HTTPError as e:
            return e.code, ""
        except Exception as e:  # noqa: BLE001
            return -1, f"transport: {e}"

        # Strip XML/HTML tags and collapse whitespace.
        class _StripTags(_hp.HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
            def handle_data(self, data: str) -> None:
                self.parts.append(data)
        parser = _StripTags()
        parser.feed(xhtml)
        text = " ".join(parser.parts)
        text = _re.sub(r"\s+", " ", text).strip()
        return 200, text[:maxChars]

    def _sparql_find_en_expr(work_uri: str) -> str | None:
        """Query CELLAR SPARQL to find the EN expression URI for a work URI."""
        import urllib.request as _ureq
        import urllib.parse as _up
        import json as _json

        uuid = work_uri.rstrip("/").split("/")[-1]
        q = (
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
            "SELECT ?expr WHERE { "
            f"  <http://publications.europa.eu/resource/cellar/{uuid}> "
            "  cdm:is_realized_by ?expr . "
            "  ?expr cdm:expression_uses_language "
            "        <http://publications.europa.eu/resource/authority/language/ENG> . "
            "} LIMIT 1"
        )
        url = "https://publications.europa.eu/webapi/rdf/sparql?" + _up.urlencode(
            {"query": q, "format": "json"}
        )
        req = _ureq.Request(
            url,
            headers={
                "Accept": "application/sparql-results+json",
                "User-Agent": "Mozilla/5.0 (compatible; etzhayyim-legal-corpus/1.0)",
            },
        )
        try:
            with _ureq.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read())
            bindings = data.get("results", {}).get("bindings", [])
            if bindings:
                expr_uri = bindings[0]["expr"]["value"]
                expr_uuid = expr_uri.rstrip("/").split("/")[-1].split(".")[0]
                return f"https://publications.europa.eu/resource/cellar/{expr_uuid}"
        except Exception:  # noqa: BLE001
            pass
        return None

    if sourceId == "eur-lex" or "publications.europa.eu" in canonicalUri:
        status, text = await asyncio.to_thread(_fetch_eur_lex_xhtml, canonicalUri)
        if status == 200 and text.strip():
            return {"bodyText": text, "chars": len(text), "status": status}
        # 404 from work URI — the work may only have non-EN manifestations.
        # Fall back: SPARQL lookup to find the EN expression UUID, then retry.
        if status in (404, 406):
            en_uri = await asyncio.to_thread(_sparql_find_en_expr, canonicalUri)
            if en_uri and en_uri != canonicalUri:
                status2, text2 = await asyncio.to_thread(_fetch_eur_lex_xhtml, en_uri)
                if status2 == 200 and text2.strip():
                    return {
                        "bodyText": text2,
                        "chars": len(text2),
                        "status": status2,
                        "resolvedUri": en_uri,
                    }
        return {"error": f"eur-lex fetch {status}", "bodyText": "", "status": status}

    return {"error": f"unsupported sourceId={sourceId!r}", "bodyText": ""}


# task_resource_flow_detect_anomaly moved to kotodama/primitives/resource_flow.py


async def main() -> None:
    LOG.info("zeebe_worker starting, gateway=%s", GATEWAY)
    worker_profile = os.environ.get("ZEEBE_WORKER_PROFILE", "").strip().lower()
    if (
        not os.environ.get("VULTR_SERVERLESS_KEY")
        and worker_profile not in {
            "open_adnetwork",
            "open-adnetwork",
            "yoro_open_adnetwork",
            "yoro-open-adnetwork",
            "business_profit",
            "business-profit",
            "yoro_business",
            "yoro-business",
            "hume_emotion",
            "hume-emotion",
            "hume",
            "legal_entity",
            "legal-entity",
            "public_malak",
            "public-malak",
            "mailer",
            "etzhayyim-project-mailer",
            "training",
            "training_actor",
            "mitama_training",
            "mitama-training",
            "billing",
            "mitama_billing",
            "mitama-billing",
            "ki",
            "ki_worker",
            "ki-worker",
            "saikin",
            "saikin_worker",
            "saikin-worker",
            "yata",
            "yatabase",
            "yata_storage",
            "yata-storage",
        }
    ):
        LOG.warning("VULTR_SERVERLESS_KEY not set — every job will fail")

    # gRPC keepalive — LangServer's default is just keepalive_time_ms=45_000 with
    # no timeout, no permit-without-calls, and no reconnect backoff override.
    # Under broker load (Vultr LB + many concurrent activate_jobs streams) the
    # connection silently transitions to "Channel is closed" and LangServer never
    # reconnects. The watchdog catches this case and exits the pod, but a
    # well-tuned keepalive reduces the recycle frequency.
    #
    # Zeebe sends GOAWAY ENHANCE_YOUR_CALM ("too_many_pings") if the client
    # pings more than once per 60s without any active streams. Keep the ping
    # interval at 120s so we stay well clear of that limit even during the
    # ~10s CPU-bound embedding window (legal.corpus.embedText).
    #
    #   - keepalive_time 120s: below Zeebe's 60s minimum-between-pings floor.
    #   - keepalive_time_ms 300s: 5-minute inter-ping floor. Zeebe gateway
    #     enforces a per-connection minimum; 120s was triggering ENHANCE_YOUR_CALM
    #     GOAWAY (too_many_pings) which cascaded into DEADLINE_EXCEEDED storms on
    #     all pollers. 300s is safely above the gateway's default 30s minimum.
    #   - keepalive_timeout_ms 20s: bounded ack wait before declaring dead.
    #   - permit_without_calls 0: suppress keepalive pings when no RPC is
    #     in-flight. Between ActivateJobs calls the pollers are idle; pinging
    #     idle channels multiplies the ping rate by the number of registered
    #     task types and overwhelms the gateway.
    #   - http2.max_pings_without_data 0: unlimited (default 2 then close).
    #   - min_time_between_pings / min_ping_interval 300s: match keepalive_time.
    #   - reconnect_backoff 1s..10s: LangServer defaults to 20s..120s; our
    #     broker is in-cluster so faster reconnect is appropriate.
    GRPC_CHANNEL_OPTIONS = (
        ("grpc.keepalive_time_ms", 300_000),
        ("grpc.keepalive_timeout_ms", 20_000),
        ("grpc.keepalive_permit_without_calls", 0),
        ("grpc.http2.max_pings_without_data", 0),
        ("grpc.http2.min_time_between_pings_ms", 300_000),
        ("grpc.http2.min_ping_interval_without_data_ms", 300_000),
        ("grpc.initial_reconnect_backoff_ms", 1_000),
        ("grpc.min_reconnect_backoff_ms", 1_000),
        ("grpc.max_reconnect_backoff_ms", 10_000),
    )
    channel = create_langserver_channel(grpc_address=GATEWAY, channel_options=GRPC_CHANNEL_OPTIONS)
    worker = LangServerWorker(channel)

    if worker_profile in {"yata", "yatabase", "yata_storage", "yata-storage"}:
        # yatabase.etzhayyim.com dedicated worker (ADR-2605080000 §D10/§D12-D24).
        # Subscribes to all `yata.*` task types: storage put/get/delete/presign/list,
        # multipart, metering rollup, embedding drain, tier migrate, multipart reap,
        # database provision, sparql.run, cypher.run, plus the shared
        # `generic.audit.emit` task that yata BPMN processes chain into.
        from kotodama.primitives.yata_storage import register as _yata_storage_register  # noqa: E402

        _yata_storage_register(worker, timeout_ms=60_000)
        worker.task(
            task_type="generic.audit.emit",
            single_value=False,
            timeout_ms=60_000,
        )(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "yata.{storage.{put,get,delete,presign,list_objects,metering.rollup,"
            "embedding.drain,tier.migrate,multipart.{init,part,complete,abort,reap}},"
            "database.provision,sparql.run,cypher.run},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        await channel.close()
        LOG.info("zeebe_worker stopped cleanly (yata profile)")
        return

    if worker_profile in {"mailer", "etzhayyim-project-mailer"}:
        for _mailer_task, _mailer_fn, _mailer_timeout in (
            ("health", "health", 30_000),
            ("listEmails", "list_emails", 30_000),
            ("listBindings", "list_bindings", 30_000),
            ("stats", "stats", 30_000),
            ("sendEmail", "send_email", 120_000),
            ("provisionMailbox", "provision_mailbox", 120_000),
            ("handleCommit", "handle_commit", 30_000),
            ("heartbeat", "heartbeat", 30_000),
        ):
            worker.task(task_type=f"mailer.{_mailer_task}", single_value=False, timeout_ms=_mailer_timeout)(_make_mailer_task(_mailer_fn))
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "mailer.{health,listEmails,listBindings,stats,sendEmail,provisionMailbox,handleCommit,heartbeat}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        await channel.close()
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"llm_knowledge", "llm-knowledge", "knowledge"}:
        knowledge_timeout_ms = int(os.environ.get("LLM_KNOWLEDGE_JOB_TIMEOUT_MS", "660000"))
        worker.task(task_type="llm.knowledge.retrieve", single_value=False, timeout_ms=60_000)(task_llm_knowledge_retrieve)
        worker.task(task_type="llm.knowledge.langgraphAnswer", single_value=False, timeout_ms=knowledge_timeout_ms)(task_llm_knowledge_langgraph_answer)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "llm.knowledge.retrieve,llm.knowledge.langgraphAnswer",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"yoro_actor_quality", "yoro-social", "yoro_social"}:
        from kotodama.primitives import yoro_social  # noqa: E402

        yoro_social.register(worker, timeout_ms=90_000)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "yoro.actorQuality.inspect,yoro.actorQuality.verify,"
            "yoro.actorQuality.enrichProfile,"
            "yoro.actorQuality.ensureSeedPost",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"open_adnetwork", "open-adnetwork", "yoro_open_adnetwork", "yoro-open-adnetwork"}:
        timeout_ms = int(os.environ.get("OPEN_ADNETWORK_JOB_TIMEOUT_MS", "90000"))
        worker.task(task_type="generic.db.select", single_value=False, timeout_ms=timeout_ms)(task_generic_db_select)
        worker.task(task_type="generic.db.insert", single_value=False, timeout_ms=timeout_ms)(task_generic_db_insert)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=timeout_ms)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "generic.db.select,generic.db.insert,generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"business_profit", "business-profit", "yoro_business", "yoro-business"}:
        timeout_ms = int(os.environ.get("BUSINESS_PROFIT_JOB_TIMEOUT_MS", "180000"))
        worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(task_rw_health_probe)
        worker.task(
            task_type="business.profit.settleOpenAdnetwork",
            single_value=False,
            timeout_ms=timeout_ms,
            max_jobs_to_activate=1,
            max_running_jobs=1,
        )(task_business_profit_settle_open_adnetwork)
        business_task_types = ["rw.health.probe", "business.profit.settleOpenAdnetwork"]
        if os.environ.get("REGISTER_BLOCKCHAIN_TASKS", "0").lower() in ("1", "true", "on", "yes"):
            worker.task(
                task_type="blockchain.head.ingest",
                single_value=False,
                timeout_ms=180_000,
                max_jobs_to_activate=1,
                max_running_jobs=1,
            )(task_blockchain_head_ingest)
            business_task_types.append("blockchain.head.ingest")
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        business_task_types.append("generic.audit.emit")
        LOG.info(
            "registered dedicated worker profile=%s task_types=%s",
            worker_profile,
            ",".join(business_task_types),
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"legal_entity", "legal-entity"}:
        from kotodama.primitives import legal_entity  # noqa: E402

        timeout_ms = int(os.environ.get("LEGAL_ENTITY_JOB_TIMEOUT_MS", "180000"))
        max_jobs_to_activate = int(os.environ.get("LEGAL_ENTITY_MAX_JOBS_TO_ACTIVATE", "1"))
        max_running_jobs = int(os.environ.get("LEGAL_ENTITY_MAX_RUNNING_JOBS", "1"))
        registry_suffixes = [
            suffix.strip()
            for suffix in os.environ.get("LEGAL_ENTITY_REGISTRY_SUFFIXES", "").split(",")
            if suffix.strip()
        ]
        include_gleif = os.environ.get("LEGAL_ENTITY_INCLUDE_GLEIF", "1").lower() in ("1", "true", "on", "yes")
        include_edgar = os.environ.get("LEGAL_ENTITY_INCLUDE_EDGAR", "1").lower() in ("1", "true", "on", "yes")
        legal_entity.register(
            worker,
            timeout_ms=timeout_ms,
            max_jobs_to_activate=max_jobs_to_activate,
            max_running_jobs=max_running_jobs,
            registry_suffixes=registry_suffixes,
            include_gleif=include_gleif,
            include_edgar=include_edgar,
        )
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s legal_entity_registry_suffixes=%s "
            "include_gleif=%s include_edgar=%s task_types=legalEntity.*,generic.audit.emit",
            worker_profile,
            ",".join(registry_suffixes) if registry_suffixes else "*",
            include_gleif,
            include_edgar,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"shosha", "sogo_shosha", "sogo-shosha"}:
        # Dedicated shosha.etzhayyim.com worker (T2 sogo-shosha actor, ADR-0056 +
        # ADR-2604282300). Registers shosha.* primitives + the two generic
        # primitives shosha BPMN depends on (audit emit + pds.dispatch for
        # social derive in tradeIdeaSynthesize / dailyShoshaReport).
        from kotodama.primitives import shosha  # noqa: E402

        shosha_timeout_ms = int(os.environ.get("SHOSHA_JOB_TIMEOUT_MS", "60000"))
        shosha.register(worker, timeout_ms=shosha_timeout_ms)
        worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=60_000)(task_generic_pds_dispatch)
        LOG.info(
            "registered dedicated worker profile=%s task_types=shosha.*,generic.{audit.emit,pds.dispatch}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"iryo", "hospital", "iryo_hospital", "iryo-hospital"}:
        # Dedicated iryo.etzhayyim.com worker (T2 hospital operations actor,
        # ADR-2605080800 + ADR-0036 + ADR-0056 + ADR-2604282300, Phase 1).
        # Registers iryo.* primitives + the two generic primitives that
        # iryo BPMN depends on (audit emit + pds.dispatch).
        from kotodama.primitives import iryo  # noqa: E402

        iryo_timeout_ms = int(os.environ.get("IRYO_JOB_TIMEOUT_MS", "60000"))
        iryo.register(worker, timeout_ms=iryo_timeout_ms)
        worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=60_000)(task_generic_pds_dispatch)
        LOG.info(
            "registered dedicated worker profile=%s task_types=iryo.*,generic.{audit.emit,pds.dispatch}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"lifehack", "lifehack_actor", "mitama_lifehack", "mitama-lifehack"}:
        # Dedicated lifehack.etzhayyim.com worker (T2 household life-hack actor,
        # ADR-0036 + ADR-0056 + ADR-2604282300, Phase 1 dust prevention).
        # Registers lifehack.* primitives + the two generic primitives
        # lifehack BPMN depends on (audit emit + pds.dispatch for the
        # daily dust post and static-electricity alert).
        from kotodama.primitives import lifehack  # noqa: E402

        lifehack_timeout_ms = int(os.environ.get("LIFEHACK_JOB_TIMEOUT_MS", "60000"))
        lifehack.register(worker, timeout_ms=lifehack_timeout_ms)
        worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=60_000)(task_generic_pds_dispatch)
        LOG.info(
            "registered dedicated worker profile=%s task_types=lifehack.*,generic.{audit.emit,pds.dispatch}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"otakiage", "otakiage_actor", "mitama_otakiage", "mitama-otakiage"}:
        # Dedicated otakiage.etzhayyim.com worker (T2 Reuse & Ritual Platform,
        # ADR-2605081700 + ADR-0036 + ADR-0056 + ADR-2604282300).
        # Registers otakiage.* primitives + the two generic primitives
        # otakiage BPMN depends on (audit emit + pds.dispatch for
        # socialAnnounce T1 derive on handover/ritual completion).
        from kotodama.primitives import otakiage  # noqa: E402

        otakiage_timeout_ms = int(os.environ.get("OTAKIAGE_JOB_TIMEOUT_MS", "60000"))
        otakiage.register(worker, timeout_ms=otakiage_timeout_ms)
        worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=60_000)(task_generic_pds_dispatch)
        LOG.info(
            "registered dedicated worker profile=%s task_types=otakiage.*,generic.{audit.emit,pds.dispatch}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"training", "training_actor", "mitama_training", "mitama-training"}:
        # Dedicated training.etzhayyim.com worker (T2 model training actor,
        # ADR-2605070700 + ADR-0056 + ADR-2604282300). Registers train.*
        # primitives + the one generic primitive training BPMNs depend
        # on (audit emit). Heavy GPU tasks (sft / lora / distill) lazy-
        # import transformers / peft / datasets / torch — CPU-only pods
        # in this profile only fail when a GPU task fires.
        from kotodama.primitives import training_run  # noqa: E402

        training_timeout_ms = int(os.environ.get("TRAINING_JOB_TIMEOUT_MS", "1800000"))
        training_run.register(worker, timeout_ms=training_timeout_ms)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types=train.{dataset.snapshot,teacher.label,sft.run,lora.run,distill.run,eval.run,promote.checkpoint,list.{runs,checkpoints,snapshots,serving},coverage.snapshot},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"chat", "chat_agent", "chat-agent"}:
        # Dedicated etzhayyim.com chat maintenance worker (T2 chat actor,
        # ADR-2604282300 + ADR 260413 Path F + ADR-0049). Registers only
        # the cron-bound + side-effect primitives; the agent hot path runs
        # in `kotodama.chat_server` (separate Deployment).
        from kotodama.primitives import chat as _chat  # noqa: E402

        chat_timeout_ms = int(os.environ.get("CHAT_JOB_TIMEOUT_MS", "120000"))
        _chat.register(worker, timeout_ms=chat_timeout_ms)
        worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=60_000)(task_generic_pds_dispatch)
        LOG.info(
            "registered dedicated worker profile=%s task_types=chat.*,generic.{audit.emit,pds.dispatch}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"animeka"}:
        # Dedicated animeka.etzhayyim.com worker (T2 anime production actor,
        # ADR-0056 + ADR-2604282300). Registers animeka.* CRUD task
        # types + the generic primitives the 12 generation BPMNs depend
        # on (script/storyboard/layout/keyframe/inbetween/colorModel/
        # autoTrace/background/composite/soundCue/publishEpisode/chat).
        # Isolation rationale: shared zeebe-worker is saturated (~200
        # task types, watchdog ping fail, animeka jobs starved → 0
        # `animeka_*` instances since 2026-04-30 broker restart).
        animeka_timeout_ms = int(os.environ.get("ANIMEKA_JOB_TIMEOUT_MS", "60000"))
        comfyui_timeout_ms = int(os.environ.get("ANIMEKA_COMFYUI_TIMEOUT_MS", "600000"))
        # CRUD (13 types)
        worker.task(task_type="animeka.createWork",        single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_create_work)
        worker.task(task_type="animeka.listWorks",         single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_list_works)
        worker.task(task_type="animeka.addEpisode",        single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_add_episode)
        worker.task(task_type="animeka.listEpisodes",      single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_list_episodes)
        worker.task(task_type="animeka.publishEpisodeApp", single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_publish_episode_app)
        worker.task(task_type="animeka.addCut",            single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_add_cut)
        worker.task(task_type="animeka.listCuts",          single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_list_cuts)
        worker.task(task_type="animeka.getCut",            single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_get_cut)
        worker.task(task_type="animeka.updateCutStage",    single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_update_cut_stage)
        worker.task(task_type="animeka.submitRetake",      single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_submit_retake)
        worker.task(task_type="animeka.resolveRetake",     single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_resolve_retake)
        worker.task(task_type="animeka.listRetakes",       single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_list_retakes)
        worker.task(task_type="animeka.health",            single_value=False, timeout_ms=animeka_timeout_ms)(task_animeka_health)
        # Generic primitives that animeka generation BPMN ServiceTasks
        # bind to (see 00-contracts/bpmn/com/etzhayyim/animeka/*.bpmn).
        worker.task(task_type="generic.llm.chat",     single_value=False, timeout_ms=120_000)(task_generic_llm_chat)
        worker.task(task_type="generic.llm.json",     single_value=False, timeout_ms=120_000)(task_generic_llm_json)
        worker.task(task_type="generic.db.select",    single_value=False, timeout_ms=60_000)(task_generic_db_select)
        worker.task(task_type="generic.db.insert",    single_value=False, timeout_ms=60_000)(task_generic_db_insert)
        worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=60_000)(task_generic_pds_dispatch)
        worker.task(task_type="generic.http.fetch",   single_value=False, timeout_ms=120_000)(task_generic_http_fetch)
        worker.task(task_type="generic.comfyui.call", single_value=False, timeout_ms=comfyui_timeout_ms)(task_generic_comfyui_call)
        LOG.info(
            "registered dedicated worker profile=%s task_types=animeka.*(13),generic.{llm.chat,llm.json,db.select,db.insert,audit.emit,pds.dispatch,http.fetch,comfyui.call}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"shinshi"}:
        # Dedicated shinshi.etzhayyim.com worker (T2 sensitive-content cosplay
        # platform, ADR-0056 + ADR-2604282300). Registers shinshi.scene.*
        # + shinshi.video.* + shinshi.coverage.* task types + the small
        # set of generic primitives the 6 BPMNs depend on
        # (audit.emit / db.select / db.insert).
        # Isolation rationale: parity with mitama-shosha-pool (Phase 2c.5)
        # and mitama-animeka-pool — shared zeebe-worker is saturated
        # (~200 task types) and a long shinshi.scene.bulkSeed run blocks
        # other actors. SDXL render = up to 25s/scene × 5 scenes × 3
        # slugs = ~6 min per bulk seed; Wan 2.2 i2v = 9 min per render.
        shinshi_timeout_ms = int(os.environ.get("SHINSHI_JOB_TIMEOUT_MS", "60000"))
        shinshi_render_timeout_ms = int(os.environ.get("SHINSHI_RENDER_TIMEOUT_MS", "180000"))
        shinshi_bulk_timeout_ms = int(os.environ.get("SHINSHI_BULK_TIMEOUT_MS", "900000"))
        shinshi_video_timeout_ms = int(os.environ.get("SHINSHI_VIDEO_TIMEOUT_MS", "540000"))
        # shinshi.scene.* (SDXL via ComfyUI + AT post, C-path)
        from kotodama.primitives import shinshi_image  # noqa: E402
        from kotodama.primitives.shinshi_image import (
            task_shinshi_scene_render,
            task_shinshi_scene_bulk_seed,
            task_shinshi_coverage_find_incomplete,
        )
        worker.task(
            task_type="shinshi.scene.render",
            single_value=False,
            timeout_ms=shinshi_render_timeout_ms,
        )(task_shinshi_scene_render)
        worker.task(
            task_type="shinshi.scene.bulkSeed",
            single_value=False,
            timeout_ms=shinshi_bulk_timeout_ms,
        )(task_shinshi_scene_bulk_seed)
        worker.task(
            task_type="shinshi.coverage.findIncomplete",
            single_value=False,
            timeout_ms=60_000,
        )(task_shinshi_coverage_find_incomplete)
        # shinshi.video.* (Wan 2.2 i2v via ComfyUI + AT post)
        from kotodama.primitives import shinshi_video  # noqa: E402
        shinshi_video.register(worker, timeout_ms=shinshi_video_timeout_ms)
        # Generic primitives that shinshi BPMN ServiceTasks bind to
        # (see 00-contracts/bpmn/com/etzhayyim/shinshi/*.bpmn —
        # generic.audit.emit / generic.db.select / generic.db.insert).
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.db.select",  single_value=False, timeout_ms=60_000)(task_generic_db_select)
        worker.task(task_type="generic.db.insert",  single_value=False, timeout_ms=60_000)(task_generic_db_insert)
        LOG.info(
            "registered dedicated worker profile=%s task_types=shinshi.{scene.render,scene.bulkSeed,coverage.findIncomplete,video.render},generic.{audit.emit,db.select,db.insert}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"billing", "mitama_billing", "mitama-billing"}:
        # Dedicated billing.etzhayyim.com worker (T2 retail cloud metering /
        # rollup / invoice / discount, ADR-2605080000 + ADR-0056 +
        # ADR-2604282300). Registers billing.{event,rollup,detect,
        # generate,discount,credit,usage,quota,invoice,coverage}.* task
        # types + the small set of generic primitives the 5 BPMNs depend
        # on (audit.emit / db.select / db.insert).
        # Isolation rationale: parity with mitama-shosha-pool / shinshi
        # / animeka — billing rollup_daily and generate_invoice may
        # process 10K+ org rows in a single tick; sharing the busy
        # zeebe-worker would starve unrelated actors during the burst.
        billing_timeout_ms = int(os.environ.get("BILLING_JOB_TIMEOUT_MS", "60000"))
        from kotodama.primitives import billing as billing_module  # noqa: E402

        billing_module.register(worker, timeout_ms=billing_timeout_ms)
        # Generic primitives that billing BPMN ServiceTasks bind to
        # (see 00-contracts/bpmn/com/etzhayyim/billing/*.bpmn —
        # generic.audit.emit / generic.db.select / generic.db.insert).
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.db.select",  single_value=False, timeout_ms=60_000)(task_generic_db_select)
        worker.task(task_type="generic.db.insert",  single_value=False, timeout_ms=60_000)(task_generic_db_insert)
        LOG.info(
            "registered dedicated worker profile=%s task_types=billing.{event.record,rollup.daily,rollup.monthly,detect.overage,generate.invoice,discount.{validateRole,apply},credit.apply,usage.get,quota.status,invoice.{list,get},coverage.snapshot},generic.{audit.emit,db.select,db.insert}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"hume_emotion", "hume-emotion", "hume"}:
        timeout_ms = int(os.environ.get("HUME_EMOTION_JOB_TIMEOUT_MS", "180000"))
        distill_timeout_ms = int(os.environ.get("HUME_DISTILLATION_JOB_TIMEOUT_MS", "900000"))
        from kotodama.primitives import hume_emotion  # noqa: E402
        from kotodama.primitives import hume_distillation  # noqa: E402
        from kotodama.agents.hume_emotion import task_agent_hume_emotion  # noqa: E402

        async def task_hume_generic_langgraph_run(
            graph_id: str = "",
            state: dict | None = None,
            mode: str = "oneshot",
            config: dict | None = None,
        ) -> dict:
            from kotodama.primitives import langgraph_registry  # noqa: E402
            import kotodama.agents.hume_emotion  # noqa: E402, F401

            graph = langgraph_registry.get(graph_id)
            if graph is None:
                return {"error": f"unknown graph_id: {graph_id!r}", "registered": langgraph_registry.list_ids()}
            result = await graph.ainvoke(state or {}, config or {})
            return dict(result)

        hume_emotion.register(worker, timeout_ms=timeout_ms)
        hume_distillation.register(worker, timeout_ms=distill_timeout_ms)
        worker.task(
            task_type="com.etzhayyim.agent.hume.emotion",
            single_value=False,
            timeout_ms=timeout_ms,
        )(task_agent_hume_emotion)
        worker.task(
            task_type="generic.langgraph.run",
            single_value=False,
            timeout_ms=timeout_ms,
        )(task_hume_generic_langgraph_run)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "hume.expression.{predictStudent,analyzeTeacher,analyze,analyzeMultimodal,analyzeUploaded},"
            "hume.tts.synthesize,hume.distill.*,com.etzhayyim.agent.hume.emotion,generic.langgraph.run",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"webya"}:
        # webya.etzhayyim.com — ホームページ生成 actor (T3, ADR-2605080600 LangGraph Server).
        # LangGraph-routed: createSite / reviseSite は dispatcher が直接 POST /runs.
        # Zeebe-executed: domainSslMonitor (R/PT30M) + seoAudit (cron MON).
        # Isolation rationale: site generation holds a LangGraph run for up to 5 min
        # (5+ LLM calls × sequential + Jinja2 rendering); shared worker would starve
        # other actors. Follows precedent: mitama-shosha-pool, mitama-shinshi-pool.
        from kotodama.primitives import webya  # noqa: E402
        from kotodama.langgraph_graphs import webya_site_generation  # noqa: E402
        webya_site_generation.register(None)  # register LangGraph graphs

        webya_timeout_ms = int(os.environ.get("WEBYA_JOB_TIMEOUT_MS", "60000"))
        webya_ssl_timeout_ms = int(os.environ.get("WEBYA_SSL_TIMEOUT_MS", "30000"))
        webya_seo_timeout_ms = int(os.environ.get("WEBYA_SEO_TIMEOUT_MS", "300000"))

        worker.task(task_type="webya.domain.provision",       single_value=False, timeout_ms=webya_timeout_ms)(webya.task_webya_domain_provision)
        worker.task(task_type="webya.domain.checkAllPending", single_value=False, timeout_ms=webya_ssl_timeout_ms)(webya.task_webya_domain_check_all_pending)
        worker.task(task_type="webya.seo.auditAllSites",      single_value=False, timeout_ms=webya_seo_timeout_ms)(webya.task_webya_seo_audit_all_sites)
        worker.task(task_type="webya.coverage",               single_value=False, timeout_ms=webya_timeout_ms)(webya.task_webya_coverage)
        worker.task(task_type="webya.getSite",                single_value=False, timeout_ms=webya_timeout_ms)(webya.task_webya_get_site)
        worker.task(task_type="webya.getSitePreview",         single_value=False, timeout_ms=webya_timeout_ms)(webya.task_webya_get_site_preview)
        worker.task(task_type="webya.listSites",              single_value=False, timeout_ms=webya_timeout_ms)(webya.task_webya_list_sites)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        worker.task(task_type="generic.db.select",  single_value=False, timeout_ms=60_000)(task_generic_db_select)
        worker.task(task_type="generic.db.insert",  single_value=False, timeout_ms=60_000)(task_generic_db_insert)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "webya.{domain.provision,domain.checkAllPending,seo.auditAllSites,coverage,getSite,getSitePreview,listSites},"
            "generic.{audit.emit,db.select,db.insert}",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"ki", "ki_worker", "ki-worker"}:
        from kotodama.ki_worker_main import (  # noqa: E402
            task_absorb as _ki_absorb,
            task_synthesize as _ki_synthesize,
            task_bloom as _ki_bloom,
            task_ring as _ki_ring,
        )

        ki_timeout_ms = int(os.environ.get("KI_TASK_TIMEOUT_MS", "180000"))
        worker.task(task_type="ki.absorb",     single_value=False, timeout_ms=ki_timeout_ms)(_ki_absorb)
        worker.task(task_type="ki.synthesize", single_value=False, timeout_ms=ki_timeout_ms)(_ki_synthesize)
        worker.task(task_type="ki.bloom",      single_value=False, timeout_ms=ki_timeout_ms)(_ki_bloom)
        worker.task(task_type="ki.ring",       single_value=False, timeout_ms=ki_timeout_ms)(_ki_ring)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types=ki.{absorb,synthesize,bloom,ring},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"saikin", "saikin_worker", "saikin-worker"}:
        from kotodama.saikin_worker_main import (  # noqa: E402
            task_probe_environment as _saikin_probe,
            task_transfer_signal as _saikin_transfer,
            task_form_colony as _saikin_colony,
            task_lyse as _saikin_lyse,
            task_handoff_to_ki as _saikin_handoff,
        )

        saikin_timeout_ms = int(os.environ.get("SAIKIN_TASK_TIMEOUT_MS", "120000"))
        worker.task(task_type="saikin.probe_environment", single_value=False, timeout_ms=saikin_timeout_ms)(_saikin_probe)
        worker.task(task_type="saikin.transfer_signal",   single_value=False, timeout_ms=saikin_timeout_ms)(_saikin_transfer)
        worker.task(task_type="saikin.form_colony",       single_value=False, timeout_ms=saikin_timeout_ms)(_saikin_colony)
        worker.task(task_type="saikin.lyse",              single_value=False, timeout_ms=saikin_timeout_ms)(_saikin_lyse)
        worker.task(task_type="saikin.handoff_to_ki",     single_value=False, timeout_ms=saikin_timeout_ms)(_saikin_handoff)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "saikin.{probe_environment,transfer_signal,form_colony,lyse,handoff_to_ki},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"completer", "completer_worker", "completer-worker"}:
        from kotodama.completer_worker_main import (  # noqa: E402
            task_query_rules as _completer_query_rules,
            task_match_rules as _completer_match_rules,
            task_llm_evaluate as _completer_llm_evaluate,
            task_evaluate as _completer_evaluate,
            task_evaluate_repo_dids as _completer_evaluate_repo_dids,
            task_remediate as _completer_remediate,
            task_get_audit_report as _completer_get_audit_report,
            task_list_findings as _completer_list_findings,
            task_list_audits as _completer_list_audits,
            task_get_compliance_score as _completer_get_compliance_score,
        )

        completer_timeout_ms = int(os.environ.get("COMPLETER_TASK_TIMEOUT_MS", "300000"))
        completer_llm_timeout_ms = int(os.environ.get("COMPLETER_LLM_TIMEOUT_MS", "300000"))
        worker.task(task_type="com.etzhayyim.apps.completer.queryRules",        single_value=False, timeout_ms=completer_timeout_ms)(_completer_query_rules)
        worker.task(task_type="com.etzhayyim.apps.completer.matchRules",         single_value=False, timeout_ms=completer_timeout_ms)(_completer_match_rules)
        worker.task(task_type="com.etzhayyim.apps.completer.llmEvaluate",        single_value=False, timeout_ms=completer_llm_timeout_ms)(_completer_llm_evaluate)
        worker.task(task_type="com.etzhayyim.apps.completer.evaluate",           single_value=False, timeout_ms=completer_timeout_ms)(_completer_evaluate)
        worker.task(task_type="com.etzhayyim.apps.completer.evaluateRepoDids",   single_value=False, timeout_ms=completer_timeout_ms)(_completer_evaluate_repo_dids)
        worker.task(task_type="com.etzhayyim.apps.completer.remediate",          single_value=False, timeout_ms=completer_llm_timeout_ms)(_completer_remediate)
        worker.task(task_type="com.etzhayyim.apps.completer.getAuditReport",     single_value=False, timeout_ms=completer_timeout_ms)(_completer_get_audit_report)
        worker.task(task_type="com.etzhayyim.apps.completer.listFindings",       single_value=False, timeout_ms=completer_timeout_ms)(_completer_list_findings)
        worker.task(task_type="com.etzhayyim.apps.completer.listAudits",         single_value=False, timeout_ms=completer_timeout_ms)(_completer_list_audits)
        worker.task(task_type="com.etzhayyim.apps.completer.getComplianceScore", single_value=False, timeout_ms=completer_timeout_ms)(_completer_get_compliance_score)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "com.etzhayyim.apps.completer.{queryRules,matchRules,llmEvaluate,evaluate,evaluateRepoDids,"
            "remediate,getAuditReport,listFindings,listAudits,getComplianceScore},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"newsletter", "newsletter_worker", "newsletter-worker"}:
        from kotodama.newsletter_worker_main import (  # noqa: E402
            task_run_curation_agent as _newsletter_run_curation,
            task_send_via_resend as _newsletter_send,
            task_create_sponsor_slot as _newsletter_sponsor,
        )

        newsletter_timeout_ms = int(os.environ.get("NEWSLETTER_TASK_TIMEOUT_MS", "180000"))
        worker.task(task_type="newsletter.run_curation_agent", single_value=False, timeout_ms=newsletter_timeout_ms)(_newsletter_run_curation)
        worker.task(task_type="newsletter.send_via_resend",    single_value=False, timeout_ms=120_000)(_newsletter_send)
        worker.task(task_type="newsletter.create_sponsor_slot", single_value=False, timeout_ms=30_000)(_newsletter_sponsor)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "newsletter.{run_curation_agent,send_via_resend,create_sponsor_slot},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    if worker_profile in {"webmk", "webmk_worker", "webmk-worker"}:
        from kotodama.webmk_worker_main import (  # noqa: E402
            task_run_proposal_agent as _webmk_run_proposal,
            task_deliver_via_resend as _webmk_deliver,
            task_create_ad_campaign as _webmk_ad_campaign,
        )

        webmk_timeout_ms = int(os.environ.get("WEBMK_TASK_TIMEOUT_MS", "180000"))
        worker.task(task_type="webmk.run_proposal_agent", single_value=False, timeout_ms=webmk_timeout_ms)(_webmk_run_proposal)
        worker.task(task_type="webmk.deliver_via_resend", single_value=False, timeout_ms=60_000)(_webmk_deliver)
        worker.task(task_type="webmk.create_ad_campaign", single_value=False, timeout_ms=30_000)(_webmk_ad_campaign)
        worker.task(task_type="generic.audit.emit", single_value=False, timeout_ms=60_000)(task_generic_audit_emit)
        LOG.info(
            "registered dedicated worker profile=%s task_types="
            "webmk.{run_proposal_agent,deliver_via_resend,create_ad_campaign},generic.audit.emit",
            worker_profile,
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        work_task = asyncio.create_task(worker.work())
        watchdog_task = asyncio.create_task(_watchdog(channel, stop))
        activation_task = asyncio.create_task(_activation_monitor(stop))
        LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
        LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
        await stop.wait()
        LOG.info("shutdown requested")
        work_task.cancel()
        watchdog_task.cancel()
        activation_task.cancel()
        for t in (work_task, watchdog_task, activation_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        try:
            from kotodama.db_sync import close_sync_pool

            close_sync_pool()
        except Exception:
            pass
        LOG.info("zeebe_worker stopped cleanly")
        return

    # `single_value=False` so the worker returns a dict that becomes the
    # job's output variables (vs the default which extracts a single value
    # and stores it under a fixed name).
    # `timeout_ms` is the per-job lock duration the worker negotiates with
    # LangServer at invoke-time. LangServer's default (~30s) is shorter than a
    # cold Vultr Devstral storyboard call (~10-15s + intermittent timeout
    # retry), so jobs were getting re-activated mid-flight and the
    # subsequent CompleteJob came back JobNotFound. 180s gives 3x headroom
    # over the worst path including one llm.py retry.
    LONG_TIMEOUT_MS = 180_000
    worker.task(task_type="com.etzhayyim.devstral.chat",       single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_chat)
    worker.task(task_type="com.etzhayyim.devstral.classifyT3", single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_classify_t3)
    worker.task(task_type="com.etzhayyim.devstral.translate",  single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_translate)
    worker.task(task_type="com.etzhayyim.devstral.storyboard", single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_storyboard)
    worker.task(task_type="llm.knowledge.retrieve", single_value=False, timeout_ms=60_000)(task_llm_knowledge_retrieve)
    worker.task(task_type="llm.knowledge.langgraphAnswer", single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_llm_knowledge_langgraph_answer)
    from kotodama.primitives import hume_emotion  # noqa: E402
    hume_emotion.register(worker, timeout_ms=LONG_TIMEOUT_MS)
    # Phase Z-α — kotoba-kotodama.shinka.* heartbeat tasks (BPMN migration of the
    # LangGraph nodes). Shorter timeout; these are DB-bound + at most one
    # llm call inside compose.
    SHINKA_TIMEOUT_MS = 90_000
    worker.task(task_type="kotoba-kotodama.shinka.loadAndResolve", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_shinka_load_and_resolve)
    worker.task(task_type="kotoba-kotodama.shinka.compose",        single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_shinka_compose)
    worker.task(task_type="kotoba-kotodama.shinka.writeHeartbeat", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_shinka_write_heartbeat)
    worker.task(task_type="kotoba-kotodama.shinka.emitEvolution",  single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_shinka_emit_evolution)
    # F1 — generic primitives (BPMN-as-actor architecture). Same lock
    # window as devstral tasks because llm.json may sit through one
    # 20s retry on intermittent upstream timeout.
    worker.task(task_type="generic.db.select", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_select)
    worker.task(task_type="generic.db.insert", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_insert)
    worker.task(task_type="generic.db.delete", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_delete)
    worker.task(task_type="generic.db.purgeFuyouPii",  single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_fuyou_pii)
    worker.task(task_type="generic.db.purgeEpfoPii",   single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_epfo_pii)
    worker.task(task_type="generic.db.purgeEsicPii",   single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_esic_pii)
    worker.task(task_type="generic.db.purgeItr1Pii",   single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_itr1_pii)
    worker.task(task_type="generic.db.purgeGstr3bPii", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_gstr3b_pii)
    worker.task(task_type="generic.db.purgeSeiyakuConfidential", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_seiyaku_confidential)
    worker.task(task_type="generic.db.bulkInsert",               single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_bulk_insert)
    worker.task(task_type="generic.db.purgeDatacenterAccessPii", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_db_purge_datacenter_access_pii)
    worker.task(task_type="generic.llm.chat",  single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_generic_llm_chat)
    worker.task(task_type="generic.llm.json",  single_value=False, timeout_ms=LONG_TIMEOUT_MS)(task_generic_llm_json)
    worker.task(task_type="generic.rules.evaluate", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_rules_evaluate)
    # F1+ — pds / http / audit
    worker.task(task_type="generic.pds.dispatch", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_pds_dispatch)
    worker.task(task_type="generic.xrpc.invoke",  single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_xrpc_invoke)
    worker.task(task_type="generic.http.fetch",   single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_http_fetch)
    worker.task(task_type="generic.tls.probe",    single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_tls_probe)
    worker.task(task_type="generic.audit.emit",   single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_generic_audit_emit)
    worker.task(task_type="ind.efiling.submit",   single_value=False, timeout_ms=180_000)(task_ind_efiling_submit)
    worker.task(task_type="com.etzhayyim.kouza.syncDueConnections", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_kouza_sync_due_connections)
    worker.task(task_type="ingest.run.markCompleted", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_ingest_run_mark_completed)
    if os.environ.get("REGISTER_BLOCKCHAIN_TASKS", "0").lower() in ("1", "true", "on", "yes"):
        worker.task(
            task_type="blockchain.head.ingest",
            single_value=False,
            timeout_ms=180_000,
            max_jobs_to_activate=1,
            max_running_jobs=2,
        )(task_blockchain_head_ingest)
    # ADR 2604251024 — ingest-safety primitive. Runs the canonical
    # 3-point health gate script (SELECT 1 / compute age / B2 SlowDown
    # rate) so BPMN processes can skip INSERT during degraded windows.
    # Convention: `[[conventions]] rw-health-gate-before-ingest`.
    worker.task(task_type="rw.health.probe", single_value=False, timeout_ms=60_000)(task_rw_health_probe)
    # Netintel ingest tasks (DNS delta / IP enrich / WHOIS / scan banner / fingerprint).
    worker.task(task_type="netintel.dns.delta",         single_value=False, timeout_ms=300_000)(task_netintel_dns_delta)
    worker.task(task_type="netintel.ip.enrich",         single_value=False, timeout_ms=300_000)(task_netintel_ip_enrich)
    worker.task(task_type="netintel.whois.delta",       single_value=False, timeout_ms=300_000)(task_netintel_whois_delta)
    worker.task(task_type="netintel.scan.banner",       single_value=False, timeout_ms=300_000)(task_netintel_scan_banner)
    worker.task(task_type="netintel.fingerprint.delta", single_value=False, timeout_ms=300_000)(task_netintel_fingerprint_delta)
    # Bluesky AppView ingest. CF Worker is now a thin dispatcher proxy; polling
    # and graph writes run here.
    worker.task(task_type="bluesky.ingest.actor",          single_value=False, timeout_ms=120_000)(task_bluesky_ingest_actor)
    worker.task(task_type="bluesky.ingest.refreshStalest", single_value=False, timeout_ms=300_000)(task_bluesky_refresh_stalest)
    # Briefing: real-time WebRTC edge handlers remain in the CF Worker; NLP,
    # agenda validation, analytics, and decision records run here.
    worker.task(task_type="briefing.createAgenda",       single_value=False, timeout_ms=60_000)(task_briefing_create_agenda)
    worker.task(task_type="briefing.saveTranscript",     single_value=False, timeout_ms=120_000)(task_briefing_save_transcript)
    worker.task(task_type="briefing.extractActionItems", single_value=False, timeout_ms=120_000)(task_briefing_extract_action_items)
    worker.task(task_type="briefing.generateSummary",    single_value=False, timeout_ms=120_000)(task_briefing_generate_summary)
    worker.task(task_type="briefing.recordSpeakerTurn",  single_value=False, timeout_ms=30_000)(task_briefing_record_speaker_turn)
    worker.task(task_type="briefing.recordDecision",     single_value=False, timeout_ms=30_000)(task_briefing_record_decision)
    # Arbitrage leaf XRPC handlers. The arb Worker is now only a dispatcher
    # proxy; quote ingest, spread detection, proposal writes, scoring, and
    # publication records run here.
    worker.task(task_type="arb.scoutQuotes",    single_value=False, timeout_ms=120_000)(task_arb_scout_quotes)
    worker.task(task_type="arb.ingestQuote",    single_value=False, timeout_ms=30_000)(task_arb_ingest_quote)
    worker.task(task_type="arb.detectSpread",   single_value=False, timeout_ms=30_000)(task_arb_detect_spread)
    worker.task(task_type="arb.proposeTrade",   single_value=False, timeout_ms=30_000)(task_arb_propose_trade)
    worker.task(task_type="arb.scoreProposal",  single_value=False, timeout_ms=30_000)(task_arb_score_proposal)
    worker.task(task_type="arb.publishProposal", single_value=False, timeout_ms=120_000)(task_arb_publish_proposal)
    worker.task(task_type="arb.listProposals",  single_value=False, timeout_ms=30_000)(task_arb_list_proposals)
    worker.task(task_type="arb.getProposal",    single_value=False, timeout_ms=30_000)(task_arb_get_proposal)
    # Arms registry/custody. CF Worker is only a dispatcher proxy.
    worker.task(task_type="arms.registerFirearm",      single_value=False, timeout_ms=60_000)(task_arms_register_firearm)
    worker.task(task_type="arms.authenticateHolder",   single_value=False, timeout_ms=60_000)(task_arms_authenticate_holder)
    worker.task(task_type="arms.verifyAuthChallenge",  single_value=False, timeout_ms=60_000)(task_arms_verify_auth_challenge)
    worker.task(task_type="arms.issuePermit",          single_value=False, timeout_ms=60_000)(task_arms_issue_permit)
    worker.task(task_type="arms.transferCustody",      single_value=False, timeout_ms=60_000)(task_arms_transfer_custody)
    worker.task(task_type="arms.checkOutFirearm",      single_value=False, timeout_ms=60_000)(task_arms_check_out_firearm)
    worker.task(task_type="arms.checkInFirearm",       single_value=False, timeout_ms=60_000)(task_arms_check_in_firearm)
    worker.task(task_type="arms.reportIncident",       single_value=False, timeout_ms=60_000)(task_arms_report_incident)
    worker.task(task_type="arms.getFirearm",           single_value=False, timeout_ms=30_000)(task_arms_get_firearm)
    worker.task(task_type="arms.listFirearms",         single_value=False, timeout_ms=30_000)(task_arms_list_firearms)
    worker.task(task_type="arms.listPermits",          single_value=False, timeout_ms=30_000)(task_arms_list_permits)
    worker.task(task_type="arms.getAuditLog",          single_value=False, timeout_ms=30_000)(task_arms_get_audit_log)
    # Collector network intelligence. CF Worker remains a thin XRPC facade;
    # RDAP/DNS, blockchain lookup, CDX collection, scan ingest, and dashboard
    # reads execute through BPMN + Zeebe Python workers.
    worker.task(task_type="collector.collectNetintelDns",   single_value=False, timeout_ms=120_000)(task_collector_collect_netintel_dns)
    worker.task(task_type="collector.collectBlockchainBtc", single_value=False, timeout_ms=120_000)(task_collector_collect_blockchain_btc)
    worker.task(task_type="collector.collectBlockchainEth", single_value=False, timeout_ms=120_000)(task_collector_collect_blockchain_eth)
    worker.task(task_type="collector.collectCommonCrawl",   single_value=False, timeout_ms=120_000)(task_collector_collect_common_crawl)
    worker.task(task_type="collector.collectArchive",       single_value=False, timeout_ms=120_000)(task_collector_collect_archive)
    worker.task(task_type="collector.ingestScanResult",     single_value=False, timeout_ms=30_000)(task_collector_ingest_scan_result)
    worker.task(task_type="collector.triggerRun",           single_value=False, timeout_ms=120_000)(task_collector_trigger_run)
    worker.task(task_type="collector.getDashboard",         single_value=False, timeout_ms=30_000)(task_collector_get_dashboard)
    worker.task(task_type="collector.listJobs",             single_value=False, timeout_ms=30_000)(task_collector_list_jobs)
    # Calendar. CF Worker serves UI/OAuth redirect only; event, RSVP,
    # recurrence, and Google Calendar sync logic runs here.
    worker.task(task_type="calendar.createEvent",      single_value=False, timeout_ms=30_000)(task_calendar_create_event)
    worker.task(task_type="calendar.updateEvent",      single_value=False, timeout_ms=30_000)(task_calendar_update_event)
    worker.task(task_type="calendar.deleteEvent",      single_value=False, timeout_ms=30_000)(task_calendar_delete_event)
    worker.task(task_type="calendar.listEvents",       single_value=False, timeout_ms=30_000)(task_calendar_list_events)
    worker.task(task_type="calendar.getEvent",         single_value=False, timeout_ms=30_000)(task_calendar_get_event)
    worker.task(task_type="calendar.createRecurring",  single_value=False, timeout_ms=30_000)(task_calendar_create_recurring)
    worker.task(task_type="calendar.rsvp",             single_value=False, timeout_ms=30_000)(task_calendar_rsvp)
    worker.task(task_type="calendar.listInvitations",  single_value=False, timeout_ms=30_000)(task_calendar_list_invitations)
    worker.task(task_type="calendar.connectAccount",   single_value=False, timeout_ms=30_000)(task_calendar_connect_account)
    worker.task(task_type="calendar.oauthCallback",    single_value=False, timeout_ms=120_000)(task_calendar_oauth_callback)
    worker.task(task_type="calendar.syncFromGoogle",   single_value=False, timeout_ms=180_000)(task_calendar_sync_from_google)
    worker.task(task_type="calendar.cronTick",         single_value=False, timeout_ms=180_000)(task_calendar_cron_tick)
    # Animeka appview CRUD. The 12 generation stages already have BPMN
    # definitions; UI work/episode/cut/retake endpoints now execute here too.
    worker.task(task_type="animeka.createWork",      single_value=False, timeout_ms=30_000)(task_animeka_create_work)
    worker.task(task_type="animeka.listWorks",       single_value=False, timeout_ms=30_000)(task_animeka_list_works)
    worker.task(task_type="animeka.addEpisode",      single_value=False, timeout_ms=30_000)(task_animeka_add_episode)
    worker.task(task_type="animeka.listEpisodes",    single_value=False, timeout_ms=30_000)(task_animeka_list_episodes)
    worker.task(task_type="animeka.publishEpisodeApp", single_value=False, timeout_ms=30_000)(task_animeka_publish_episode_app)
    worker.task(task_type="animeka.addCut",          single_value=False, timeout_ms=30_000)(task_animeka_add_cut)
    worker.task(task_type="animeka.listCuts",        single_value=False, timeout_ms=30_000)(task_animeka_list_cuts)
    worker.task(task_type="animeka.getCut",          single_value=False, timeout_ms=30_000)(task_animeka_get_cut)
    worker.task(task_type="animeka.updateCutStage",  single_value=False, timeout_ms=30_000)(task_animeka_update_cut_stage)
    worker.task(task_type="animeka.submitRetake",    single_value=False, timeout_ms=30_000)(task_animeka_submit_retake)
    worker.task(task_type="animeka.resolveRetake",   single_value=False, timeout_ms=30_000)(task_animeka_resolve_retake)
    worker.task(task_type="animeka.listRetakes",     single_value=False, timeout_ms=30_000)(task_animeka_list_retakes)
    worker.task(task_type="animeka.health",          single_value=False, timeout_ms=30_000)(task_animeka_health)
    # Google Workspace lite appviews. connectAccount/oauthCallback share the
    # unified gworkspace_lite OAuth path; syncFromGoogle/cronTick dispatch to
    # per-service ingest modules in kotodama.ingest.<app> (drive/contacts/
    # tasks/docs/sheets/slides/meet), each of which writes typed rows into
    # vertex_g<service>_* via Drive changes cursor or service-specific API.
    for _gw_app in ("tasks", "sheets", "drive", "contacts", "meet", "docs", "slides"):
        worker.task(task_type=f"{_gw_app}.connectAccount", single_value=False, timeout_ms=30_000)(_make_gworkspace_lite_task(_gw_app, "connect_account"))
        worker.task(task_type=f"{_gw_app}.oauthCallback", single_value=False, timeout_ms=120_000)(_make_gworkspace_lite_task(_gw_app, "oauth_callback"))
        worker.task(task_type=f"{_gw_app}.syncFromGoogle", single_value=False, timeout_ms=300_000)(_make_gworkspace_service_task(_gw_app, "sync_from_google"))
        worker.task(task_type=f"{_gw_app}.cronTick", single_value=False, timeout_ms=300_000)(_make_gworkspace_service_task(_gw_app, "cron_tick"))
    for _gmail_task, _gmail_fn, _gmail_timeout in (
        ("connectAccount", "connect_account", 30_000),
        ("oauthCallback", "oauth_callback", 120_000),
        ("disconnectAccount", "disconnect_account", 30_000),
        ("syncInbox", "sync_inbox", 180_000),
        ("sendEmail", "send_email", 120_000),
        ("replyToThread", "reply_to_thread", 120_000),
        ("listAccounts", "list_accounts", 30_000),
        ("listThreads", "list_threads", 30_000),
        ("searchEmails", "search_emails", 30_000),
        ("getThread", "get_thread", 120_000),
        ("triage", "triage", 30_000),
        ("cronTick", "cron_tick", 180_000),
    ):
        worker.task(task_type=f"gmail.{_gmail_task}", single_value=False, timeout_ms=_gmail_timeout)(_make_gmail_task(_gmail_fn))
    for _outlook_task, _outlook_fn, _outlook_timeout in (
        ("getOauthConfig", "get_oauth_config", 30_000),
        ("getAuthStatus", "get_auth_status", 30_000),
        ("startAuth", "start_auth", 30_000),
        ("exchangeCode", "exchange_code", 120_000),
        ("getConnection", "get_connection", 30_000),
        ("syncMailbox", "sync_mailbox", 120_000),
        ("disconnect", "disconnect", 30_000),
        ("cardHome", "card_home", 30_000),
        ("cardCompose", "card_compose", 30_000),
        ("cardAction", "card_action", 30_000),
        ("triage", "triage", 240_000),
    ):
        worker.task(task_type=f"outlook.{_outlook_task}", single_value=False, timeout_ms=_outlook_timeout)(_make_outlook_task(_outlook_fn))

    # outlook.email.route — email→projector convo routing (pregel pipeline)
    from kotodama.primitives import email_route as _email_route
    _email_route.register(worker, timeout_ms=60_000)

    for _credits_task, _credits_fn, _credits_timeout in (
        ("checkSpendAllowed", "check_spend_allowed", 30_000),
        ("spendCredits", "spend_credits", 30_000),
        ("rewardFromCompute", "reward_from_compute", 30_000),
        ("rewardFromHC", "reward_from_hc", 30_000),
        ("processCommitSpend", "process_commit_spend", 30_000),
        ("heartbeat", "heartbeat", 30_000),
    ):
        worker.task(task_type=f"credits.{_credits_task}", single_value=False, timeout_ms=_credits_timeout)(_make_credits_task(_credits_fn))
    for _mailer_task, _mailer_fn, _mailer_timeout in (
        ("health", "health", 30_000),
        ("listEmails", "list_emails", 30_000),
        ("listBindings", "list_bindings", 30_000),
        ("stats", "stats", 30_000),
        ("sendEmail", "send_email", 120_000),
        ("provisionMailbox", "provision_mailbox", 120_000),
        ("handleCommit", "handle_commit", 30_000),
        ("heartbeat", "heartbeat", 30_000),
    ):
        worker.task(task_type=f"mailer.{_mailer_task}", single_value=False, timeout_ms=_mailer_timeout)(_make_mailer_task(_mailer_fn))
    for _stripe_task, _stripe_fn, _stripe_timeout in (
        ("createCardholder", "create_cardholder", 120_000),
        ("issueCard", "issue_card", 120_000),
        ("assignCardCredits", "assign_card_credits", 120_000),
        ("getCardCredits", "get_card_credits", 30_000),
        ("handleAuthorization", "handle_authorization", 120_000),
        ("getCard", "get_card", 30_000),
        ("listCards", "list_cards", 30_000),
        ("freezeCard", "freeze_card", 120_000),
        ("unfreezeCard", "unfreeze_card", 120_000),
        ("cancelCard", "cancel_card", 120_000),
        ("updateSpendingLimit", "update_spending_limit", 120_000),
        ("listTransactions", "list_transactions", 30_000),
        ("getCardholder", "get_cardholder", 30_000),
        ("wave", "wave", 30_000),
        ("stats", "stats", 30_000),
        ("handleCommit", "handle_commit", 30_000),
    ):
        worker.task(task_type=f"stripe.{_stripe_task}", single_value=False, timeout_ms=_stripe_timeout)(_make_stripe_task(_stripe_fn))
    # oshinobi.payment.charge — Stripe PaymentIntent confirm for tip + subscription.
    from kotodama.primitives.oshinobi import register as _oshinobi_register  # noqa: E402
    _oshinobi_register(worker, timeout_ms=30_000)
    for _ads_task, _ads_fn, _ads_timeout in (
        ("createCampaign", "create_campaign", 120_000),
        ("postSponsored", "post_sponsored", 120_000),
        ("listCampaigns", "list_campaigns", 30_000),
    ):
        worker.task(task_type=f"ads.{_ads_task}", single_value=False, timeout_ms=_ads_timeout)(_make_ads_task(_ads_fn))
    for _shiharai_task, _shiharai_fn, _shiharai_timeout in (
        ("extractBill", "extract_bill", 30_000),
        ("listPendingBills", "list_pending_bills", 30_000),
        ("preparePayment", "prepare_payment", 120_000),
        ("confirmPayment", "confirm_payment", 120_000),
        ("registerRecurring", "register_recurring", 120_000),
        ("listRecurring", "list_recurring", 30_000),
        ("getJobStatus", "get_job_status", 30_000),
    ):
        worker.task(task_type=f"shiharai.{_shiharai_task}", single_value=False, timeout_ms=_shiharai_timeout)(_make_shiharai_task(_shiharai_fn))
    for _kouza_task, _kouza_fn, _kouza_timeout in (
        ("registerConnection", "register_connection", 120_000),
        ("syncConnection", "sync_connection", 120_000),
        ("createFinancialAccount", "create_financial_account", 120_000),
        ("importStatement", "import_statement", 120_000),
        ("importStatementCsv", "import_statement_csv", 120_000),
        ("attachDocument", "attach_document", 120_000),
        ("mapKaikeiAccount", "map_kaikei_account", 30_000),
        ("listAccounts", "list_accounts", 30_000),
        ("listTransactions", "list_transactions", 30_000),
    ):
        worker.task(task_type=f"kouza.{_kouza_task}", single_value=False, timeout_ms=_kouza_timeout)(_make_kouza_task(_kouza_fn))
    for _kaikei_task, _kaikei_fn, _kaikei_timeout in (
        ("getTrialBalance", "get_trial_balance", 30_000),
        ("listJournalEntries", "list_journal_entries", 30_000),
        ("listAccounts", "list_accounts", 30_000),
        ("getMonthlySummary", "get_monthly_summary", 30_000),
        ("recordPfPayable", "record_pf_payable", 120_000),
        ("recordEsiPayable", "record_esi_payable", 120_000),
        ("recordGstPayable", "record_gst_payable", 120_000),
        ("recordAdvanceTax", "record_advance_tax", 120_000),
        ("recomputeWithholding", "recompute_withholding", 120_000),
        ("mapAccount", "map_account", 120_000),
    ):
        worker.task(task_type=f"kaikei.{_kaikei_task}", single_value=False, timeout_ms=_kaikei_timeout)(_make_kaikei_task(_kaikei_fn))
    for _mf_prefix, _mf_task, _mf_fn, _mf_timeout in (
        ("seikyu", "issueInvoice", "issue_invoice", 120_000),
        ("seikyu", "sendInvoice", "send_invoice", 30_000),
        ("seikyu", "voidInvoice", "void_invoice", 30_000),
        ("seikyu", "recordPaymentReceived", "record_payment_received", 120_000),
        ("seikyu", "listInvoices", "list_invoices", 30_000),
        ("seikyu", "getInvoiceAging", "get_invoice_aging", 30_000),
        ("seikyu", "submitPeppol", "submit_peppol", 30_000),
        ("keiyaku", "draftAgreement", "draft_agreement", 120_000),
        ("keiyaku", "submitForSignature", "submit_for_signature", 30_000),
        ("keiyaku", "signAgreement", "sign_agreement", 30_000),
        ("keiyaku", "voidAgreement", "void_agreement", 30_000),
        ("keiyaku", "listActiveAgreements", "list_active_agreements", 30_000),
        ("kousuu", "createProject", "create_project", 120_000),
        ("kousuu", "recordTimeEntry", "record_time_entry", 120_000),
        ("kousuu", "approveTimeEntry", "approve_time_entry", 30_000),
        ("kousuu", "getProjectBurn", "get_project_burn", 30_000),
        ("keihi", "submitExpense", "submit_expense", 120_000),
        ("keihi", "approveExpense", "approve_expense", 120_000),
        ("jinji", "upsertEmployee", "upsert_employee", 120_000),
        ("jinji", "recordAttendance", "record_attendance", 120_000),
        ("jinji", "completePayrollRun", "complete_payroll_run", 120_000),
        ("kaikei", "generateStatutoryReport", "generate_statutory_report", 120_000),
        ("kaikei", "validateMoneyForwardParity", "validate_moneyforward_parity", 120_000),
        ("kaisya", "registerSaasAsset", "register_saas_asset", 120_000),
        ("jinji", "recordYearEndAdjustment", "record_year_end_adjustment", 120_000),
        ("jinji", "registerMynumberVaultRef", "register_mynumber_vault_ref", 120_000),
    ):
        worker.task(task_type=f"{_mf_prefix}.{_mf_task}", single_value=False, timeout_ms=_mf_timeout)(_make_moneyforward_task(_mf_fn))
    for _ka_task, _ka_fn in (
        ("getDashboard", "get_dashboard"),
        ("getGoals", "get_goals"),
        ("getActions", "get_actions"),
        ("getRevenue", "get_revenue"),
        ("getBurn", "get_burn"),
        ("getRisks", "get_risks"),
        ("getCases", "get_cases"),
        ("getKpi", "get_kpi"),
        ("getProjects", "get_projects"),
        ("getInfra", "get_infra"),
        ("getMilestones", "get_milestones"),
        ("getSnapshots", "get_snapshots"),
        ("getTopo", "get_topo"),
        ("getInbox", "get_inbox"),
    ):
        worker.task(task_type=f"ka.{_ka_task}", single_value=False, timeout_ms=30_000)(_make_ka_task(_ka_fn))
    for _kg_task, _kg_fn, _kg_timeout in (
        ("analyzeCoverage", "analyze_coverage", 120_000),
        ("expandTitle", "expand_title", 300_000),
        ("status", "status", 30_000),
    ):
        worker.task(task_type=f"kgCurator.{_kg_task}", single_value=False, timeout_ms=_kg_timeout)(_make_kg_curator_task(_kg_fn))
    for _demining_task, _demining_fn, _demining_timeout in (
        ("registerHazardArea", "register_hazard_area", 120_000),
        ("listHazardAreas", "list_hazard_areas", 30_000),
        ("recordDetection", "record_detection", 120_000),
        ("recordClearanceTask", "record_clearance_task", 120_000),
        ("releaseArea", "release_area", 120_000),
        ("recordEoreSession", "record_eore_session", 120_000),
        ("recordVictim", "record_victim", 120_000),
    ):
        worker.task(task_type=f"demining.{_demining_task}", single_value=False, timeout_ms=_demining_timeout)(_make_demining_task(_demining_fn))
    for _dns_task, _dns_fn, _dns_timeout in (
        ("transferFromSquarespace", "transfer_from_squarespace", 120_000),
        ("transferOutcome", "transfer_outcome", 120_000),
    ):
        worker.task(task_type=f"dns.{_dns_task}", single_value=False, timeout_ms=_dns_timeout)(_make_dns_task(_dns_fn))
    for _kg_task, _kg_fn in (
        ("submitScore", "submit_score"),
        ("getLeaderboard", "get_leaderboard"),
    ):
        worker.task(task_type=f"kamiKetsuGorilla.{_kg_task}", single_value=False, timeout_ms=30_000)(_make_kami_ketsu_gorilla_task(_kg_fn))
    for _re_task, _re_fn in (
        ("searchListings", "search_listings"),
        ("getProperty", "get_property"),
        ("getMarketStats", "get_market_stats"),
    ):
        worker.task(task_type=f"realEstate.{_re_task}", single_value=False, timeout_ms=30_000)(_make_real_estate_task(_re_fn))
    for _mold_task, _mold_fn, _mold_timeout in (
        ("seedAllergenCatalog", "seed_allergen_catalog", 120_000),
        ("recordAirSampling", "record_air_sampling", 30_000),
        ("proposeSlitCandidate", "propose_slit_candidate", 30_000),
        ("listAllergens", "list_allergens", 30_000),
        ("listSlitCandidates", "list_slit_candidates", 30_000),
    ):
        worker.task(task_type=f"moldAllergy.{_mold_task}", single_value=False, timeout_ms=_mold_timeout)(_make_mold_allergy_task(_mold_fn))
    for _kami_eng_task, _kami_eng_fn in (
        ("eda.createSchematic", "eda_create_schematic"),
        ("eda.runErc", "eda_run_erc"),
        ("eda.exportGerber", "eda_export_gerber"),
        ("cad.createModel", "cad_create_model"),
        ("cad.addFeature", "cad_add_feature"),
        ("cad.exportStep", "cad_export_step"),
        ("cam.createJob", "cam_create_job"),
        ("cam.generateGcode", "cam_generate_gcode"),
        ("rtl.parseHdl", "rtl_parse_hdl"),
        ("rtl.simulate", "rtl_simulate"),
        ("rtl.synthesize", "rtl_synthesize"),
        ("cae.generateMesh", "cae_generate_mesh"),
        ("cae.runAnalysis", "cae_run_analysis"),
        ("cae.getResults", "cae_get_results"),
    ):
        worker.task(task_type=f"kamiEng.{_kami_eng_task}", single_value=False, timeout_ms=30_000)(_make_kami_eng_task(_kami_eng_fn))
    for _i18n_task, _i18n_fn in (
        ("registerProject", "register_project"),
        ("translateBatch", "translate_batch"),
        ("exportMessages", "export_messages"),
        ("translateOnDemand", "translate_on_demand"),
        ("translatePage", "translate_page"),
        ("translateMessage", "translate_message"),
        ("translateSignal", "translate_signal"),
        ("widgetLookup", "widget_lookup"),
        ("widgetSuggest", "widget_suggest"),
        ("widgetApprove", "widget_approve"),
        ("getLanguageRegistry", "get_language_registry"),
        ("getTranslationStatus", "get_translation_status"),
    ):
        worker.task(task_type=f"i18n.{_i18n_task}", single_value=False, timeout_ms=30_000)(_make_i18n_task(_i18n_fn))
    for _baminiku_task, _baminiku_fn in (
        ("setAgentProfile", "set_agent_profile"),
        ("createStream", "create_stream"),
        ("updateStage", "update_stage"),
        ("recordChat", "record_chat"),
        ("recordTip", "record_tip"),
        ("enqueueTrack", "enqueue_track"),
        ("skipTrack", "skip_track"),
        ("getStreamState", "get_stream_state"),
    ):
        worker.task(task_type=f"baminiku.{_baminiku_task}", single_value=False, timeout_ms=30_000)(_make_baminiku_task(_baminiku_fn))
    for _gpu_task, _gpu_fn in (
        ("registerParticipant", "register_participant"),
        ("createUploadSession", "create_upload_session"),
        ("recordGameplayUpload", "record_gameplay_upload"),
        ("reviewUpload", "review_upload"),
        ("calculateReward", "calculate_reward"),
        ("getCampaignStatus", "get_campaign_status"),
    ):
        worker.task(task_type=f"gamePlayUploader.{_gpu_task}", single_value=False, timeout_ms=30_000)(_make_game_play_uploader_task(_gpu_fn))
    for _apps_task, _apps_fn in (
        ("registerAppListing", "register_app_listing"),
        ("updateAppListing", "update_app_listing"),
        ("listApps", "list_apps"),
        ("getAppListing", "get_app_listing"),
        ("featureApp", "feature_app"),
        ("recordInstallIntent", "record_install_intent"),
    ):
        worker.task(task_type=f"appsDirectory.{_apps_task}", single_value=False, timeout_ms=30_000)(_make_apps_directory_task(_apps_fn))
    for _nist_task, _nist_fn in (
        ("health", "health"),
        ("describe", "describe"),
        ("wave", "wave"),
    ):
        worker.task(task_type=f"nist.{_nist_task}", single_value=False, timeout_ms=30_000)(_make_nist_task(_nist_fn))
    for _vehicle_task, _vehicle_fn in (
        ("health", "health"),
        ("describe", "describe"),
        ("fileFormats", "file_formats"),
        ("planSupplyProcess", "plan_supply_process"),
    ):
        worker.task(task_type=f"vehicle.{_vehicle_task}", single_value=False, timeout_ms=30_000)(_make_vehicle_task(_vehicle_fn))
    for _vin_task, _vin_fn in (
        ("collectRecall", "collect_recall"),
        ("debugPds", "debug_pds"),
        ("decodeVin", "decode_vin"),
        ("exampleMethod", "example_method"),
        ("getManufacturer", "get_manufacturer"),
        ("getPlant", "get_plant"),
        ("getShipmentFlow", "get_shipment_flow"),
        ("getVehicle", "get_vehicle"),
        ("getVehicleHistory", "get_vehicle_history"),
        ("ingestShipment", "ingest_shipment"),
        ("listCohort", "list_cohort"),
        ("listJurisdictions", "list_jurisdictions"),
        ("listManufacturers", "list_manufacturers"),
        ("listPlants", "list_plants"),
        ("listShipmentCohorts", "list_shipment_cohorts"),
        ("listVehicleTypes", "list_vehicle_types"),
        ("listVehicles", "list_vehicles"),
        ("lookupPlate", "lookup_plate"),
        ("registerCohort", "register_cohort"),
        ("registerPlate", "register_plate"),
        ("searchVehicles", "search_vehicles"),
        ("seedJurisdictions", "seed_jurisdictions"),
        ("seedManufacturers", "seed_manufacturers"),
        ("seedProductionLines", "seed_production_lines"),
        ("seedProductionPlants", "seed_production_plants"),
        ("seedVehicleTypes", "seed_vehicle_types"),
        ("seedWmiCodes", "seed_wmi_codes"),
    ):
        worker.task(task_type=f"vin.{_vin_task}", single_value=False, timeout_ms=30_000)(_make_vin_task(_vin_fn))
    for _vessel_task, _vessel_fn in (
        ("registry.registerShip", "register_ship"),
        ("registry.updateShip", "update_ship"),
        ("registry.registerOwner", "register_owner"),
        ("registry.transferOwnership", "transfer_ownership"),
        ("registry.registerRegistry", "register_registry"),
        ("registry.changeFlag", "change_flag"),
        ("registry.getShip", "get_ship"),
        ("registry.listShips", "list_ships"),
        ("registry.searchShips", "search_ships"),
        ("registry.getOwner", "get_owner"),
        ("registry.getShipOwner", "get_ship_owner"),
        ("registry.getShipsByFlag", "get_ships_by_flag"),
        ("tracking.ingestPositions", "ingest_positions"),
        ("tracking.getVesselPosition", "get_vessel_position"),
        ("tracking.getPositionByMmsi", "get_position_by_mmsi"),
        ("tracking.listVesselsInArea", "list_vessels_in_area"),
        ("tracking.getPositionHistory", "get_position_history"),
        ("tracking.listVesselsNearPort", "list_vessels_near_port"),
        ("voyage.registerVoyage", "register_voyage"),
        ("voyage.updateVoyage", "update_voyage"),
        ("voyage.listVoyages", "list_voyages"),
        ("voyage.recordPortCall", "record_port_call"),
        ("voyage.listPortCalls", "list_port_calls"),
        ("voyage.linkOwnerEntity", "link_owner_entity"),
        ("voyage.getVesselChain", "get_vessel_chain"),
        ("seedMaritime", "seed_maritime"),
        ("getDashboard", "get_dashboard"),
    ):
        worker.task(task_type=f"vessel.{_vessel_task}", single_value=False, timeout_ms=30_000)(_make_vessel_task(_vessel_fn))
    for _port_task, _port_fn in (
        ("infrastructure.registerPort", "register_port"),
        ("infrastructure.updatePort", "update_port"),
        ("infrastructure.registerBerth", "register_berth"),
        ("infrastructure.registerTerminal", "register_terminal"),
        ("infrastructure.getPort", "get_port"),
        ("infrastructure.listPorts", "list_ports"),
        ("infrastructure.searchPorts", "search_ports"),
        ("infrastructure.getPortBerths", "get_port_berths"),
        ("infrastructure.getPortTerminals", "get_port_terminals"),
        ("portCallTracking.receivePortCallEvent", "receive_port_call_event"),
        ("portCallTracking.listPortCallEvents", "list_port_call_events"),
        ("portCallTracking.getVesselsAtPort", "get_vessels_at_port"),
        ("portCallTracking.getPortOccupancy", "get_port_occupancy"),
        ("seedPorts", "seed_ports"),
        ("getDashboard", "get_dashboard"),
    ):
        worker.task(task_type=f"port.{_port_task}", single_value=False, timeout_ms=30_000)(_make_port_task(_port_fn))
    worker.task(task_type="maps.collection.registerSource", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_source"))
    worker.task(task_type="maps.collection.listSources", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_sources"))
    worker.task(task_type="maps.collection.createCollectionJob", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("create_collection_job"))
    worker.task(task_type="maps.collection.advanceJob", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("advance_job"))
    worker.task(task_type="maps.collection.listJobs", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_jobs"))
    worker.task(task_type="maps.collection.getJobStatus", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_job_status"))
    worker.task(task_type="maps.collection.storeDataset", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("store_dataset"))
    worker.task(task_type="maps.collection.getDataset", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_dataset"))
    worker.task(task_type="maps.collection.listDatasets", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_datasets"))
    worker.task(task_type="maps.collection.getPipelineStats", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_pipeline_stats"))
    worker.task(task_type="maps.collection.importOsmPois", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("import_osm_pois"))
    worker.task(task_type="maps.collection.importWikidataPois", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("import_wikidata_pois"))
    worker.task(task_type="maps.collection.searchPoi", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("search_poi"))
    worker.task(task_type="maps.collection.getPoi", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_poi"))
    worker.task(task_type="maps.collection.listPoiTypes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_poi_types"))
    worker.task(task_type="maps.collection.registerWriterProfiles", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_writer_profiles"))
    worker.task(task_type="maps.geo.registerRegion", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_region"))
    worker.task(task_type="maps.geo.resolveGeoAlias", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("resolve_geo_alias"))
    worker.task(task_type="maps.geo.listGeoAliases", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_geo_aliases"))
    worker.task(task_type="maps.geo.listGeoSchemes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_geo_schemes"))
    worker.task(task_type="maps.geo.listVerticalZones", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_vertical_zones"))
    worker.task(task_type="maps.geo.listNaturalZones", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_natural_zones"))
    worker.task(task_type="maps.geo.listLayerCoordinators", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_layer_coordinators"))
    worker.task(task_type="maps.geo.resolveZones3d", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("resolve_zones3d"))
    worker.task(task_type="maps.place.crawlerLocations", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("crawler_locations"))
    worker.task(task_type="maps.place.searchPlaces", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("search_places"))
    worker.task(task_type="maps.place.getPlace", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_place"))
    worker.task(task_type="maps.graph.graphTraverse", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("graph_traverse"))
    worker.task(task_type="maps.graph.graphNeighbors", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("graph_neighbors"))
    worker.task(task_type="maps.graph.searchResources", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("search_resources"))
    worker.task(task_type="maps.transport.registerRoute", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_route"))
    worker.task(task_type="maps.transport.listRoutes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_routes"))
    worker.task(task_type="maps.transport.getRoute", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_route"))
    worker.task(task_type="maps.transport.registerRoad", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_road"))
    worker.task(task_type="maps.transport.listRoads", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_roads"))
    worker.task(task_type="maps.transport.registerRailway", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_railway"))
    worker.task(task_type="maps.transport.listRailways", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_railways"))
    worker.task(task_type="maps.transport.registerSeaRoute", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_sea_route"))
    worker.task(task_type="maps.transport.listSeaRoutes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_sea_routes"))
    worker.task(task_type="maps.transport.registerAirRoute", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_air_route"))
    worker.task(task_type="maps.transport.listAirRoutes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_air_routes"))
    worker.task(task_type="maps.transport.registerBusRoute", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_bus_route"))
    worker.task(task_type="maps.transport.listBusRoutes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_bus_routes"))
    worker.task(task_type="maps.infra.registerInfraNetwork", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_infra_network"))
    worker.task(task_type="maps.infra.listInfraNetworks", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_infra_networks"))
    worker.task(task_type="maps.infra.registerInfraSegment", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_infra_segment"))
    worker.task(task_type="maps.infra.listInfraSegments", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_infra_segments"))
    worker.task(task_type="maps.infra.registerInfraNode", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_infra_node"))
    worker.task(task_type="maps.infra.listInfraNodes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_infra_nodes"))
    worker.task(task_type="maps.infra.registerInfraIncident", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_infra_incident"))
    worker.task(task_type="maps.infra.listInfraIncidents", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_infra_incidents"))
    worker.task(task_type="maps.infra.infraQuery", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("infra_query"))
    worker.task(task_type="maps.infra.infraCrossSection", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("infra_cross_section"))
    worker.task(task_type="maps.geography.registerSpot", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_spot"))
    worker.task(task_type="maps.geography.listSpots", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_spots"))
    worker.task(task_type="maps.geography.getSpot", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_spot"))
    worker.task(task_type="maps.geography.spotSearch", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spot_search"))
    worker.task(task_type="maps.geography.spotRecommend", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spot_recommend"))
    worker.task(task_type="maps.geography.registerRiver", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_river"))
    worker.task(task_type="maps.geography.listRivers", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_rivers"))
    worker.task(task_type="maps.geography.registerLake", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_lake"))
    worker.task(task_type="maps.geography.listLakes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_lakes"))
    worker.task(task_type="maps.geography.registerCoastline", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_coastline"))
    worker.task(task_type="maps.geography.listCoastlines", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_coastlines"))
    worker.task(task_type="maps.geography.registerMountain", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_mountain"))
    worker.task(task_type="maps.geography.listMountains", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_mountains"))
    worker.task(task_type="maps.geography.registerMaritimeZone", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_maritime_zone"))
    worker.task(task_type="maps.geography.listMaritimeZones", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_maritime_zones"))
    worker.task(task_type="maps.geography.registerAdminArea", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_admin_area"))
    worker.task(task_type="maps.geography.listAdminAreas", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_admin_areas"))
    worker.task(task_type="maps.transportExtra.registerAircraft", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_aircraft"))
    worker.task(task_type="maps.transportExtra.upsertFlightOperation", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("upsert_flight_operation"))
    worker.task(task_type="maps.transportExtra.listFlightOperations", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_flight_operations"))
    worker.task(task_type="maps.transportExtra.registerWaterway", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_waterway"))
    worker.task(task_type="maps.transportExtra.listWaterways", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_waterways"))
    worker.task(task_type="maps.transportExtra.registerPort", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_port"))
    worker.task(task_type="maps.transportExtra.listPorts", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_ports"))
    worker.task(task_type="maps.transportExtra.registerAirport", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_airport"))
    worker.task(task_type="maps.transportExtra.listAirports", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_airports"))
    worker.task(task_type="maps.transportExtra.registerStation", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_station"))
    worker.task(task_type="maps.transportExtra.listStations", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_stations"))
    worker.task(task_type="maps.transportExtra.registerBusStop", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_bus_stop"))
    worker.task(task_type="maps.transportExtra.listBusStops", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_bus_stops"))
    worker.task(task_type="maps.transportExtra.registerParking", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_parking"))
    worker.task(task_type="maps.transportExtra.listParkings", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_parkings"))
    worker.task(task_type="maps.transportExtra.registerEvCharger", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_ev_charger"))
    worker.task(task_type="maps.transportExtra.listEvChargers", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_ev_chargers"))
    worker.task(task_type="maps.transportExtra.upsertFlightOffer", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("upsert_flight_offer"))
    worker.task(task_type="maps.transportExtra.listFlightOffers", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_flight_offers"))
    worker.task(task_type="maps.twinSensorSim.registerBuilding", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_building"))
    worker.task(task_type="maps.twinSensorSim.listBuildings", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_buildings"))
    worker.task(task_type="maps.twinSensorSim.getBuilding", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_building"))
    worker.task(task_type="maps.twinSensorSim.registerBuildingFloor", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_building_floor"))
    worker.task(task_type="maps.twinSensorSim.registerAsset", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_asset"))
    worker.task(task_type="maps.twinSensorSim.listAssets", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_assets"))
    worker.task(task_type="maps.twinSensorSim.deviceBind", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("device_bind"))
    worker.task(task_type="maps.twinSensorSim.listDevices", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_devices"))
    worker.task(task_type="maps.twinSensorSim.twinStateUpdate", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("twin_state_update"))
    worker.task(task_type="maps.twinSensorSim.twinStateGet", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("twin_state_get"))
    worker.task(task_type="maps.twinSensorSim.occupancyUpdate", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("occupancy_update"))
    worker.task(task_type="maps.twinSensorSim.registerSensor", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_sensor"))
    worker.task(task_type="maps.twinSensorSim.listSensors", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_sensors"))
    worker.task(task_type="maps.twinSensorSim.sensorIngest", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("sensor_ingest"))
    worker.task(task_type="maps.twinSensorSim.sensorQuery", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("sensor_query"))
    worker.task(task_type="maps.twinSensorSim.sensorLatest", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("sensor_latest"))
    worker.task(task_type="maps.twinSensorSim.sensorAlertSet", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("sensor_alert_set"))
    worker.task(task_type="maps.twinSensorSim.listSensorAlerts", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_sensor_alerts"))
    worker.task(task_type="maps.twinSensorSim.simulationCreate", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("simulation_create"))
    worker.task(task_type="maps.twinSensorSim.simulationRun", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("simulation_run"))
    worker.task(task_type="maps.twinSensorSim.simulationResult", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("simulation_result"))
    worker.task(task_type="maps.twinSensorSim.forecastGet", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("forecast_get"))
    worker.task(task_type="maps.twinSensorSim.healthAssess", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("health_assess"))
    worker.task(task_type="maps.twinSensorSim.maintenancePlan", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("maintenance_plan"))
    worker.task(task_type="maps.spatiotemporal.spatialEventRecord", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_event_record"))
    worker.task(task_type="maps.spatiotemporal.spatialEventQuery", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_event_query"))
    worker.task(task_type="maps.spatiotemporal.spatialVersionRecord", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_version_record"))
    worker.task(task_type="maps.spatiotemporal.spatialVersionQuery", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_version_query"))
    worker.task(task_type="maps.spatiotemporal.spatialRelationWrite", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_relation_write"))
    worker.task(task_type="maps.spatiotemporal.spatialRelationQuery", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_relation_query"))
    worker.task(task_type="maps.spatiotemporal.timeline", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("timeline"))
    worker.task(task_type="maps.spatiotemporal.spatialDiff", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("spatial_diff"))
    worker.task(task_type="maps.spatiotemporal.displayLayerDefine", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("display_layer_define"))
    worker.task(task_type="maps.spatiotemporal.listDisplayLayers", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_display_layers"))
    worker.task(task_type="maps.spatiotemporal.getDashboard", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_dashboard"))
    worker.task(task_type="maps.spatiotemporal.actorLocations", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("actor_locations"))
    worker.task(task_type="maps.registryMedia.listPostLocations", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_post_locations"))
    worker.task(task_type="maps.registryMedia.mapralyImportPoi", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("mapraly_import_poi"))
    worker.task(task_type="maps.registryMedia.mapralyListPois", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("mapraly_list_pois"))
    worker.task(task_type="maps.registryMedia.visionImportEntities", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("vision_import_entities"))
    worker.task(task_type="maps.registryMedia.listVisionResults", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_vision_results"))
    worker.task(task_type="maps.registryMedia.satelliteImportScene", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("satellite_import_scene"))
    worker.task(task_type="maps.registryMedia.listSatelliteScenes", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_satellite_scenes"))
    worker.task(task_type="maps.registryMedia.listSatelliteSources", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_satellite_sources"))
    worker.task(task_type="maps.registryMedia.listGeoDomains", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_geo_domains"))
    worker.task(task_type="maps.registryMedia.listWebCrawlGeoEntities", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_web_crawl_geo_entities"))
    worker.task(task_type="maps.registryMedia.registerLegalEntity", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_legal_entity"))
    worker.task(task_type="maps.registryMedia.listLegalEntities", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_legal_entities"))
    worker.task(task_type="maps.registryMedia.registerOperator", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_operator"))
    worker.task(task_type="maps.registryMedia.listOperators", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_operators"))
    worker.task(task_type="maps.registryMedia.registerPropertyOwner", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_property_owner"))
    worker.task(task_type="maps.registryMedia.listPropertyOwners", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_property_owners"))
    worker.task(task_type="maps.registryMedia.registerLandRegistry", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_land_registry"))
    worker.task(task_type="maps.registryMedia.listLandRegistries", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_land_registries"))
    worker.task(task_type="maps.registryMedia.registerPropertyRegistry", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_property_registry"))
    worker.task(task_type="maps.registryMedia.listPropertyRegistries", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_property_registries"))
    worker.task(task_type="maps.registryMedia.registerBusinessRegistry", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_business_registry"))
    worker.task(task_type="maps.registryMedia.listBusinessRegistries", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_business_registries"))
    worker.task(task_type="maps.registryMedia.registerConstructionPermit", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_construction_permit"))
    worker.task(task_type="maps.registryMedia.listConstructionPermits", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_construction_permits"))
    worker.task(task_type="maps.registryMedia.registerOperatingLicense", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_operating_license"))
    worker.task(task_type="maps.registryMedia.listOperatingLicenses", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_operating_licenses"))
    worker.task(task_type="maps.registryMedia.registerZoningRecord", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_zoning_record"))
    worker.task(task_type="maps.registryMedia.listZoningRecords", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("list_zoning_records"))
    worker.task(task_type="maps.registryMedia.registerOwnership", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("register_ownership"))
    worker.task(task_type="maps.registryMedia.ownershipChain", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("ownership_chain"))
    worker.task(task_type="maps.registryMedia.entityHistory", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("entity_history"))
    worker.task(task_type="maps.coverage.getCoverageStatus", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("get_coverage_status"))
    worker.task(task_type="maps.coverage.expandFrontier", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("expand_frontier"))
    worker.task(task_type="maps.coverage.refreshCoverageStats", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("refresh_coverage_stats"))
    worker.task(task_type="maps.coverage.advanceCoverage", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("advance_coverage"))
    worker.task(task_type="maps.coverage.seedAllKnownVariations", single_value=False, timeout_ms=30_000)(_make_maps_collection_task("seed_all_known_variations"))
    worker.task(task_type="maps.coverage.batchCoverageCycle", single_value=False, timeout_ms=180_000)(_make_maps_collection_task("batch_coverage_cycle"))
    worker.task(task_type="maps.coverage.runCoverageJob", single_value=False, timeout_ms=60_000)(_make_maps_collection_task("run_coverage_job"))
    # Houbun law ingest. Source-specific parsing/writes live in
    # kotodama.ingest.houbun; graph writes stay behind rw.health.probe.
    from kotodama.ingest.houbun import (  # noqa: E402
        task_houbun_acquire_cursor,
        task_houbun_advance_cursor,
        task_houbun_complete_run,
        task_houbun_create_run,
        task_houbun_fetch_egov_jpn,
        task_houbun_plan_egov_jpn,
        task_houbun_verify_visibility,
        task_houbun_write_graph,
    )
    worker.task(task_type="houbun.createRun", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_houbun_create_run)
    worker.task(task_type="houbun.egovJpn.plan", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_houbun_plan_egov_jpn)
    worker.task(task_type="houbun.acquireCursor", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_houbun_acquire_cursor)
    worker.task(task_type="houbun.egovJpn.fetch", single_value=False, timeout_ms=300_000)(task_houbun_fetch_egov_jpn)
    worker.task(task_type="houbun.writeGraph", single_value=False, timeout_ms=300_000)(task_houbun_write_graph)
    worker.task(task_type="houbun.verifyVisibility", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_houbun_verify_visibility)
    worker.task(task_type="houbun.advanceCursor", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_houbun_advance_cursor)
    worker.task(task_type="houbun.completeRun", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_houbun_complete_run)
    # Fund intel ingest (ADR-2604261200). Source-specific parsing is in
    # kotodama.ingest.fund; graph writes stay behind rw.health.probe.
    from kotodama.ingest.fund.zeebe_tasks import (  # noqa: E402
        task_fund_compute_returns,
        task_fund_enrich_entity,
        task_fund_fetch_raw,
        task_fund_normalize_fund,
        task_fund_normalize_investment,
        task_fund_normalize_lp,
        task_fund_normalize_manager,
        task_fund_persist_artifact,
        task_fund_plan_sources,
        task_fund_verify_coverage,
        task_fund_write_graph,
    )
    worker.task(
        task_type="fund.planSources",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_plan_sources)
    worker.task(
        task_type="fund.fetchRaw",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_fetch_raw)
    worker.task(
        task_type="fund.persistArtifact",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_persist_artifact)
    worker.task(
        task_type="fund.normalizeManager",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_normalize_manager)
    worker.task(
        task_type="fund.normalizeFund",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_normalize_fund)
    worker.task(
        task_type="fund.normalizeLp",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_normalize_lp)
    worker.task(
        task_type="fund.normalizeInvestment",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_normalize_investment)
    worker.task(
        task_type="fund.enrichEntity",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_enrich_entity)
    worker.task(
        task_type="fund.computeReturns",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_compute_returns)
    worker.task(
        task_type="fund.writeGraph",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_write_graph)
    worker.task(
        task_type="fund.verifyCoverage",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_fund_verify_coverage)
    # JP corporate finance ingest (ADR-2604291500). PDF/image OCR path converts
    # pages to WebP, pins them to ipfs.etzhayyim.com, then calls Gemma 4 via llm.etzhayyim.com.
    from kotodama.ingest.jp_corp_finance.zeebe_tasks import (  # noqa: E402
        task_jp_corp_finance_create_run,
        task_jp_corp_finance_extract_financial_facts,
        task_jp_corp_finance_fetch_source,
        task_jp_corp_finance_normalize,
        task_jp_corp_finance_plan_shards,
        task_jp_corp_finance_refresh_coverage,
        task_jp_corp_finance_validate_rows,
        task_jp_corp_finance_verify_visibility,
        task_jp_corp_finance_webp_ocr,
        task_jp_corp_finance_write_graph,
    )
    worker.task(
        task_type="jpCorpFinance.createRun",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_create_run)
    worker.task(
        task_type="jpCorpFinance.planShards",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_plan_shards)
    worker.task(
        task_type="jpCorpFinance.fetchSource",
        single_value=False,
        timeout_ms=300_000,
    )(task_jp_corp_finance_fetch_source)
    worker.task(
        task_type="jpCorpFinance.normalize",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_normalize)
    worker.task(
        task_type="jpCorpFinance.webpOcr",
        single_value=False,
        timeout_ms=600_000,
    )(task_jp_corp_finance_webp_ocr)
    worker.task(
        task_type="jpCorpFinance.extractFinancialFacts",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_extract_financial_facts)
    worker.task(
        task_type="jpCorpFinance.validateRows",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_validate_rows)
    worker.task(
        task_type="jpCorpFinance.writeGraph",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_write_graph)
    worker.task(
        task_type="jpCorpFinance.verifyVisibility",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_verify_visibility)
    worker.task(
        task_type="jpCorpFinance.refreshCoverage",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_jp_corp_finance_refresh_coverage)
    worker.task(
        task_type="openPatent.expiredDrugPatent.collect",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_expired_drug_patent_collect)
    worker.task(
        task_type="openPatent.expiredDrugPatent.screen",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_expired_drug_patent_screen)
    worker.task(
        task_type="openPatent.expiredDrugPatent.pipeline",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_expired_drug_patent_pipeline)
    worker.task(
        task_type="openPatent.expiredDrugPatent.recordBlocker",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_expired_drug_patent_record_blocker)
    worker.task(
        task_type="openPatent.genericManufacturing.plan",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_plan)
    worker.task(
        task_type="openPatent.genericManufacturing.prepareSeiyakuBatchDraft",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_prepare_seiyaku_batch_draft)
    worker.task(
        task_type="openPatent.genericManufacturing.validateSeiyakuBatchDraft",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_validate_seiyaku_batch_draft)
    worker.task(
        task_type="openPatent.genericManufacturing.handoffSeiyaku",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_handoff_seiyaku)
    worker.task(
        task_type="openPatent.genericManufacturing.queueSeiyakuBatchStart",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_queue_seiyaku_batch_start)
    worker.task(
        task_type="openPatent.genericManufacturing.ackSeiyakuBatchStart",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_ack_seiyaku_batch_start)
    worker.task(
        task_type="openPatent.genericManufacturing.summarizeSeiyakuStartProgress",
        single_value=False,
        timeout_ms=SHINKA_TIMEOUT_MS,
    )(task_open_patent_generic_manufacturing_summarize_seiyaku_start_progress)
    # patent.etzhayyim.com — USPTO PatentsView weekly TSV ingest + EPO + blob.convert.
    # patent.blob.convert requires poppler-utils + webp on the worker pod.
    PATENT_TIMEOUT_MS = 21_600_000  # 6h — TSV full-load can take hours
    from kotodama.primitives.patent import register as _patent_register  # noqa: E402
    _patent_register(worker, timeout_ms=PATENT_TIMEOUT_MS)
    # isbn.etzhayyim.com — Open Library / Aozora / Gutenberg / NDL / HathiTrust
    # bulk catalog + PD fulltext ingest. Hathifile + Open Library full
    # dumps can run for hours; reuse the patent 6h timeout budget.
    from kotodama.primitives.isbn import register as _isbn_register  # noqa: E402
    _isbn_register(worker, timeout_ms=PATENT_TIMEOUT_MS)
    # sbom.etzhayyim.com — registerArtifact persistence (Phase B). CF Worker
    # forwards via dispatcher; this handler does the psycopg2 INSERTs
    # into vertex_sbom_artifact + vertex_sbom_component (ADR-2604282300:
    # CF Worker stays facade-only; DB writes happen here).
    from kotodama.primitives.sbom import register as _sbom_register  # noqa: E402
    _sbom_register(worker, timeout_ms=300_000)
    # adsk.etzhayyim.com — HuggingFace dataset ingest (Phase 1: text/code only;
    # 3D / voxel blobs deferred to Phase 2 with B2). Reuse 6h budget.
    from kotodama.primitives.adsk import register as _adsk_register  # noqa: E402
    _adsk_register(worker, timeout_ms=PATENT_TIMEOUT_MS)
    # shosha.etzhayyim.com — sogo-shosha (general trading company). Pure T2:
    # autonomous BPMN-as-actor (R/PT1H intel, R/PT4H recompute + idea
    # synth, daily report) + 4 XRPC bindings (submitTrade / proposeHedge
    # / complyCheck / agentLoop). 60s default budget covers LLM tier
    # `balanced`; longer ms set per-task in shosha.register.
    from kotodama.primitives.shosha import register as _shosha_register  # noqa: E402
    _shosha_register(worker, timeout_ms=60_000)
    # lifehack.etzhayyim.com — household life-hack (Phase 1 dust prevention).
    # Pure T2: autonomous research (R/PT24H) + daily dust post (cron 09 JST)
    # + static alert (R/PT6H) + 6 XRPC bindings. 60s default; longer ms
    # set per-task in lifehack.register for LLM-heavy synth/grade.
    from kotodama.primitives.lifehack import register as _lifehack_register  # noqa: E402
    _lifehack_register(worker, timeout_ms=60_000)
    # karma.etzhayyim.com — Edge-primary Spirit-in-Physic Karma Hegemon (Phase K0).
    # Pure T2 BPMN-as-actor with 5-layer persistence pipeline (RW → AT
    # repo → IPFS self → IPFS external → blockchain anchor). Authoritative
    # axioms in 90-docs/proof/Karma.lean. 60s default; longer ms set
    # per-task for IPFS pin / Filecoin / blockchain submit.
    from kotodama.primitives.karma import register as _karma_register  # noqa: E402
    _karma_register(worker, timeout_ms=60_000)
    # karma.etzhayyim.com — evaluation agent (LangGraph + Pregel-style graph
    # propagation + actor mailbox semantics). Single task type
    # `karma.agent.evaluate` runs internal multi-node state machine.
    # LLM refinement opt-in via KARMA_AGENT_LLM=1 env var.
    from kotodama.primitives.karma_agent import register as _karma_agent_register  # noqa: E402
    _karma_agent_register(worker, timeout_ms=90_000)
    # karma.etzhayyim.com — 覚者 DAO arbitration (Phase K1). 5 task types:
    # findVoters / openArbitration / castVote / finalize / sweepExpired.
    # Triggered by karma.evaluate's 'escalate-dao' recommendation OR
    # any caller with elevated standing.
    from kotodama.primitives.karma_dao import register as _karma_dao_register  # noqa: E402
    _karma_dao_register(worker, timeout_ms=60_000)
    # karma.etzhayyim.com — witness invitation (Phase K1). 3 task types:
    # inviteFanOut / respondToInvitation / sweepExpired. Triggered by
    # karma.evaluate's 'require-witness' recommendation; invitees can
    # accept (→ vertex_karma_witness row) or decline.
    from kotodama.primitives.karma_witness import register as _karma_witness_register  # noqa: E402
    _karma_witness_register(worker, timeout_ms=60_000)
    # karma.etzhayyim.com — WBT (Well-Becoming Token) settlement (Phase K1).
    # 3 task types: balanceGet / transfer / forfeitToCommons. Backs
    # rebirth.forfeit (atomic debit + credit + log + commons pool bump).
    from kotodama.primitives.karma_wbt import register as _karma_wbt_register  # noqa: E402
    _karma_wbt_register(worker, timeout_ms=30_000)
    # karma.etzhayyim.com — resident organism agent (Phase K2 ecosystem
    # self-growth). 5 task types: spawn / tick / checkpoint / harvest /
    # dissolveRuntime. Long-running daemons that "live" in K8s pod /
    # RunPod / Ethereum substrates per vertex_organism_runtime row.
    from kotodama.primitives.karma_resident import register as _karma_resident_register  # noqa: E402
    _karma_resident_register(worker, timeout_ms=60_000)
    # karma.etzhayyim.com — zk-SNARK rebirth non-linkability proof (Phase K3).
    # 2 task types: rebirthVerify / rebirthProofLookup. Verifies Groth16
    # proof + burns nullifier on RebirthVerifier contract. Stub verifier
    # in K3; real bundler call in K4.
    from kotodama.primitives.karma_zk import register as _karma_zk_register  # noqa: E402
    _karma_zk_register(worker, timeout_ms=60_000)
    # karma.etzhayyim.com — Filecoin storage deal automation (Phase K3).
    # 3 task types: proposeBatch / renewExpiring / statusGet. L4
    # long-term backup beyond ETH anchor. Estuary/Lighthouse stub in
    # K3; real provider HTTP call in K4.
    from kotodama.primitives.karma_filecoin import register as _karma_filecoin_register  # noqa: E402
    _karma_filecoin_register(worker, timeout_ms=60_000)
    # yatabase.etzhayyim.com — integrated storage autonomous workers
    # (metering rollup / embedding queue / tier migration / multipart reap).
    from kotodama.primitives.yata_storage import register as _yata_storage_register  # noqa: E402
    _yata_storage_register(worker, timeout_ms=60_000)
    # domain.etzhayyim.com — TLD registration assistance (eligibilityCheck +
    # registerAssist + monthly catalog refresh). Pure T2 advisory: reads
    # vertex_domain_* + writes draft rows to vertex_domain_registration.
    # Lightweight (no external HTTP, no LLM in Phase 1) so the shared
    # mitama-udf pool is sufficient — no dedicated Helm release needed.
    from kotodama.primitives.domain import register as _domain_register  # noqa: E402
    _domain_register(worker, timeout_ms=30_000)
    # news.etzhayyim.com intel process tasks.
    worker.task(task_type="news.udf.scoreIntel", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_news_udf_score_intel)
    worker.task(task_type="xrpc.com.etzhayyim.apps.news.analyzeIntel", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_news_xrpc_analyze_intel)
    worker.task(task_type="xrpc.com.etzhayyim.apps.news.publishIntel", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_news_xrpc_publish_intel)
    # kakaku.etzhayyim.com price comparison actor. Source-specific logic lives in
    # kotodama.ingest.kakaku; these task types are bound directly from the
    # com.etzhayyim.apps.kakaku.* XRPC BPMN processes.
    from kotodama.ingest.kakaku import (  # noqa: E402
        task_compare_offers,
        task_ingest_offer_from_url,
        task_upsert_offer,
    )
    worker.task(task_type="xrpc.com.etzhayyim.apps.kakaku.upsertOffer", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_upsert_offer)
    worker.task(task_type="xrpc.com.etzhayyim.apps.kakaku.ingestOfferFromUrl", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_ingest_offer_from_url)
    worker.task(task_type="xrpc.com.etzhayyim.apps.kakaku.compareOffers", single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_compare_offers)
    # animeka (ADR-2604231328) — ComfyUI passthrough. 600s timeout accommodates
    # AnimateDiff / SVD / WAN 5B video generations that run 3-5 min on L40S.
    COMFYUI_TIMEOUT_MS = 600_000
    worker.task(task_type="generic.comfyui.call", single_value=False, timeout_ms=COMFYUI_TIMEOUT_MS)(task_generic_comfyui_call)
    worker.task(task_type="gyosei.source.link",   single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_gyosei_source_link)
    # Z-β — timer-driven shinka tick. Wraps the existing `shinka_tick_actor`
    # SQL UDF so a BPMN timer-start event can schedule per-actor heartbeats
    # without the K8s CronJob (templates/cronjob-shinka.yaml).
    SHINKA_TICK_TIMEOUT_MS = 180_000  # UDF includes one Devstral compose call
    worker.task(task_type="com.etzhayyim.shinka.tick", single_value=False, timeout_ms=SHINKA_TICK_TIMEOUT_MS)(task_shinka_tick)
    # Z2 — LangGraph ingest planner. 3-node graph (classify → summarise →
    # audit). Budgeted by Zeebe process timeout, not agent-internal — a
    # runaway LLM loop hits the SHINKA_TIMEOUT_MS boundary and the BPMN
    # caller retries per <zeebe:taskDefinition retries="N">.
    from kotodama.agents import task_agent_plan  # noqa: E402, lazy: skip langgraph import if unused
    worker.task(task_type="com.etzhayyim.agent.plan",  single_value=False, timeout_ms=SHINKA_TIMEOUT_MS)(task_agent_plan)
    from kotodama.agents.hume_emotion import task_agent_hume_emotion  # noqa: E402
    worker.task(task_type="com.etzhayyim.agent.hume.emotion", single_value=False,
                timeout_ms=LONG_TIMEOUT_MS)(task_agent_hume_emotion)
    # SBOM register agent — wraps task_sbom_register_artifact +
    # task_sbom_run_vuln_match in a LangGraph (classify → persist with
    # retry → notify). Callers can use com.etzhayyim.agent.sbom.register
    # instead of the lower-level xrpc.com.etzhayyim.apps.sbom.registerArtifact
    # when they want the agentic retry + notification semantics.
    from kotodama.agents.sbom_register import task_agent_sbom_register  # noqa: E402
    SBOM_AGENT_TIMEOUT_MS = 600_000
    worker.task(task_type="com.etzhayyim.agent.sbom.register", single_value=False,
                timeout_ms=SBOM_AGENT_TIMEOUT_MS)(task_agent_sbom_register)
    # Z-γ — gameka studio deliberator. 5-node LangGraph (planner →
    # researcher → critic → loop_or_finalize → finalizer). Transitional
    # task type until generic.langgraph.run lands per ADR 2604250836; see
    # ADR 2604250900 §D5 + 00-contracts/bpmn/com/etzhayyim/gameka/proposeGame.bpmn.
    GAMEKA_DELIBERATE_TIMEOUT_MS = 60_000  # 3 iter × 2 LLM × ~7s p95
    from kotodama.agents import task_agent_gameka_studio  # noqa: E402
    worker.task(task_type="com.etzhayyim.agent.gameka.studio", single_value=False,
                timeout_ms=GAMEKA_DELIBERATE_TIMEOUT_MS)(task_agent_gameka_studio)
    # Z-γ-2 — gameka codegen. Pure-function source-tree generator
    # (kami-app-{slug} crate). 30s budget covers cold imports; typical
    # render is <50ms. ADR 2604250900 §D4.2 + P2.
    GAMEKA_CODEGEN_TIMEOUT_MS = 30_000
    from kotodama.handlers.gameka_codegen import (  # noqa: E402
        task_gameka_codegen_render_kami_app,
    )
    worker.task(task_type="gameka.codegen.renderKamiApp", single_value=False,
                timeout_ms=GAMEKA_CODEGEN_TIMEOUT_MS)(task_gameka_codegen_render_kami_app)
    # Z-γ-4 — gameka avatar render. Pure-stdlib procedural identicon
    # (sha256 → 8×8 mirrored grid, biome palette, zlib-compressed RGB
    # PNG → data URI). Typical render <30ms; 30s budget headroom.
    # ADR 2604250900 §P10.
    GAMEKA_AVATAR_TIMEOUT_MS = 30_000
    from kotodama.handlers.gameka_avatar import (  # noqa: E402
        task_gameka_avatar_render,
    )
    worker.task(task_type="gameka.avatar.render", single_value=False,
                timeout_ms=GAMEKA_AVATAR_TIMEOUT_MS)(task_gameka_avatar_render)
    # shinshi.video.render — Wan 2.2 i2v via ComfyUI + AT post.
    from kotodama.primitives import shinshi_video  # noqa: E402
    shinshi_video.register(worker, timeout_ms=540_000)

    # shinshi.scene.render / shinshi.scene.bulkSeed — SDXL still-image
    # generation via ComfyUI + AT post. Replaces former CF Worker
    # `seedScenesWithImages*` and `requestScene` direct ComfyUI calls
    # (ADR-2604282300: CF Worker = edge layer only).
    from kotodama.primitives import shinshi_image  # noqa: E402
    shinshi_image.register(worker)

    # gameka.build.wasmPack — dedicated gameka-build-runner pod subscribes to
    # Zeebe directly (50-infra/vultr/gameka-build-runner/runner.py).
    # No registration here; Zeebe dispatches exclusively to the pod worker.

    # Z-γ-3 — gameka visual + perf critic. 3-node LangGraph
    # (analyze_render → analyze_match → synthesize). 60s budget covers
    # one vision-LLM call at p95 + headroom. ADR 2604250900 §P4.
    GAMEKA_VISUAL_CRITIC_TIMEOUT_MS = 60_000
    from kotodama.agents import task_agent_gameka_visual_critic  # noqa: E402
    worker.task(task_type="com.etzhayyim.agent.gameka.visualCritic", single_value=False,
                timeout_ms=GAMEKA_VISUAL_CRITIC_TIMEOUT_MS)(task_agent_gameka_visual_critic)

    # generic.langgraph.run — ADR-2604250836 step 2.
    # Dispatches to any registered LangGraph graph by graph_id.
    # Inputs: graph_id (str), state (dict), mode ("oneshot"|"stream"),
    #         config (dict, optional langgraph RunnableConfig overrides).
    # Output: flat dict of the final graph state.
    async def task_generic_langgraph_run(
        graph_id: str = "",
        state: dict | None = None,
        mode: str = "oneshot",
        config: dict | None = None,
    ) -> dict:
        from kotodama.primitives import langgraph_registry  # noqa: E402
        # Ensure gameka graph is registered (module-level side effect on import).
        import kotodama.agents.gameka_studio  # noqa: E402, F401
        import kotodama.agents.gameka_visual_critic  # noqa: E402, F401
        import kotodama.agents.hume_emotion  # noqa: E402, F401
        import kotodama.ingest.jp_corp_finance.langgraph_disclosure_extract  # noqa: E402, F401
        import kotodama.primitives.apqc  # noqa: E402, F401
        graph = langgraph_registry.get(graph_id)
        if graph is None:
            registered = langgraph_registry.list_ids()
            return {"error": f"unknown graph_id: {graph_id!r}", "registered": registered}
        result = await graph.ainvoke(state or {}, config or {})
        return dict(result)

    worker.task(task_type="generic.langgraph.run", single_value=False,
                timeout_ms=GAMEKA_DELIBERATE_TIMEOUT_MS)(task_generic_langgraph_run)

    # ADR-0057 — mangaka pipeline primitives (5 batch tasks for
    # generateEpisode.bpmn). 600s timeout accommodates 76-panel ComfyUI render
    # + 20-page Pillow compose + PDS uploadBlob × 80 (panels + pages).
    MANGAKA_TIMEOUT_MS = 600_000
    from kotodama.primitives import mangaka  # noqa: E402, lazy: skip Pillow import if unused
    mangaka.register(worker, timeout_ms=MANGAKA_TIMEOUT_MS)
    # Loading robot primitives for image-analysis-driven loading cell design.
    LOADING_ROBOT_TIMEOUT_MS = 180_000
    from kotodama.primitives import loading_robot  # noqa: E402
    loading_robot.register(worker, timeout_ms=LOADING_ROBOT_TIMEOUT_MS)
    # Robotics business-process primitives for BPMN + MCP planning.
    ROBOTICS_TIMEOUT_MS = 180_000
    from kotodama.primitives import robotics  # noqa: E402
    robotics.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # M&A brokerage actor workflow. This keeps the MA Core/APQC/ISCO/ISIC
    # orchestration in the shared Zeebe worker until heavier source-specific
    # diligence workers are split out.
    from kotodama.primitives import ma  # noqa: E402
    ma.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # Business-person public-role ingest for MA research/matching context.
    # Source-specific collectors can feed rows into this deterministic writer.
    from kotodama.primitives import business_person  # noqa: E402
    business_person.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # telecom Phase 1 (eTOM Customer + Service Provisioning) — ADR-0056
    # BPMN-as-actor. Six task types `telecom.{subscriber,sim,service,
    # usage,billing,sla}.*` write `vertex_telecom_*` rows. PII split per
    # ADR-0018 keeps raw MSISDN/IMSI in `vertex_telecom_subscriber_pii`.
    from kotodama.primitives import telecom  # noqa: E402
    telecom.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # Yoro actor social primitive. This is the graph-visible fallback that
    # mirrors the Murakumo cron job and can be driven from BPMN timers.
    from kotodama.primitives import yoro_social  # noqa: E402
    yoro_social.register(worker, timeout_ms=SHINKA_TIMEOUT_MS)
    # Projector L7 primitives (ADR-2604271600). LangGraph + LangChain
    # integration for the yoro /projects agent loop. CF Worker stays as
    # an L3 dispatcher; reasoning + tool calling + ToT/SC live here.
    from kotodama.primitives import projector  # noqa: E402
    projector.register(worker, timeout_ms=SHINKA_TIMEOUT_MS)
    # Murakumo fleet health sampler. The CF Worker keeps the HTTP gateway;
    # Zeebe owns scheduled sampling and persistence.
    from kotodama.primitives import murakumo_fleet  # noqa: E402
    murakumo_fleet.register(worker, timeout_ms=60_000)
    # Graph repo-commit consumer bridge. The CF Worker keeps canonical
    # projection code; Zeebe owns the schedule and audit trail.
    from kotodama.primitives import graph_consumer  # noqa: E402
    graph_consumer.register(worker, timeout_ms=60_000)
    # Kotodama organizer bridge. The CF dashboard keeps the classifier and R2
    # plan writes; Zeebe owns the 5-minute schedule.
    from kotodama.primitives import kotoba-kotodama_organizer  # noqa: E402
    kotoba-kotodama_organizer.register(worker, timeout_ms=90_000)
    # PDS write-outbox replay bridge. PDS keeps XRPC dispatch and Hyperdrive;
    # Zeebe owns the replay schedule.
    from kotodama.primitives import pds_outbox  # noqa: E402
    pds_outbox.register(worker, timeout_ms=90_000)
    # PDS signing key rotation bridge. PDS keeps D1/KEK access; Zeebe owns
    # the schedule and graph-visible audit event.
    from kotodama.primitives import pds_key_rotation  # noqa: E402
    pds_key_rotation.register(worker, timeout_ms=90_000)
    # PDS Mitama actor cron-trigger resync bridge. PDS keeps manifest/pipeline
    # execution; Zeebe owns the five-minute resync schedule.
    from kotodama.primitives import pds_mitama_cron  # noqa: E402
    pds_mitama_cron.register(worker, timeout_ms=90_000)
    # PDS app/shinka heartbeat bridge. PDS keeps graph lookup and HTTP fan-out;
    # Zeebe owns the five-minute schedule and audit event.
    from kotodama.primitives import pds_heartbeat  # noqa: E402
    pds_heartbeat.register(worker, timeout_ms=120_000)
    # PDS DiscoverFeed cache warm bridge. PDS keeps Cache API and Hyperdrive;
    # Zeebe owns the timer and graph-visible audit event.
    from kotodama.primitives import pds_discover_cache  # noqa: E402
    pds_discover_cache.register(worker, timeout_ms=60_000)
    # PDS domain coverage expansion bridge. PDS keeps Common Crawl, Murakumo,
    # repo writes, and social posting; Zeebe owns cadence and audit.
    from kotodama.primitives import pds_domain_coverage  # noqa: E402
    pds_domain_coverage.register(worker, timeout_ms=150_000)
    # Von Neumann coverage gap bridge. vertex_coverage_recipe stores program
    # memory that classifies each domain into ingest/infer/generate/defer.
    # etzhayyim.etzhayyim.com company-ops LangGraph submitter (Supervisor + 6 domain
    # agents: hr/finance/legal/sales/governance/personnel). T2 BPMN-as-actor
    # via etzhayyim.ops.submit task type.
    from kotodama.primitives import etzhayyim_ops  # noqa: E402
    etzhayyim_ops.register(worker)
    # etzhayyim.etzhayyim.com personnel decision pipeline (loadProfile + minimaxScore
    # + notifyDeny + writeAssignment). Wires personnelAssignmentDecide.bpmn
    # HITL workflow with Tier 3 PII RLS gate (CEO/COO/CLO read only).
    from kotodama.primitives import etzhayyim_personnel  # noqa: E402
    etzhayyim_personnel.register(worker, timeout_ms=120_000)
    # lawfirm.etzhayyim.com marketing LangGraph submitter + Stripe webhook.
    # Routes to lawfirm-marketing-ops (Supervisor + 6 specialists +
    # BCI Rule 36 compliance gate). Stripe webhook persists invoice/payment.
    from kotodama.primitives import lawfirm_marketing  # noqa: E402
    lawfirm_marketing.register(worker, timeout_ms=120_000)
    # lawfirm.etzhayyim.com e-sign request + webhook + KPI snapshot.
    # eSign provider abstraction: docusign primary, adobesign + razorpaysign
    # fallback. KPI snapshot is RLS-gated (CEO/COO/CLO).
    from kotodama.primitives import lawfirm_esign_kpi  # noqa: E402
    lawfirm_esign_kpi.register(worker, timeout_ms=60_000)
    # lawfirm.etzhayyim.com PwC clearance workflow (CEO HITL per matter).
    # Implements CEO decision D4 (2026-05-08): per-matter PwC India
    # compliance escalation, NOT auto-screen via hash list.
    from kotodama.primitives import lawfirm_pwc  # noqa: E402
    lawfirm_pwc.register(worker, timeout_ms=60_000)
    # lawfirm.etzhayyim.com sales pipeline (mail reply webhook + stage transition).
    # Microsoft Graph subscription pushes inbound replies; we match by
    # sender domain + subject thread, advance stage, audit-log.
    from kotodama.primitives import lawfirm_sales  # noqa: E402
    lawfirm_sales.register(worker, timeout_ms=60_000)
    # lawfirm.etzhayyim.com Stripe Checkout session creation (US + INR account
    # routing, dry_run when API keys absent — Day-0 default).
    from kotodama.primitives import lawfirm_checkout  # noqa: E402
    lawfirm_checkout.register(worker, timeout_ms=30_000)
    # lawfirm.etzhayyim.com MS Graph mail subscription lifecycle (ensure + R/PT24H renew).
    from kotodama.primitives import lawfirm_msgraph  # noqa: E402
    lawfirm_msgraph.register(worker, timeout_ms=60_000)
    # kaisya.etzhayyim.com per-member chat (M365 / MCP / web channels). Routes to
    # etzhayyim-company-ops or lawfirm-marketing-ops by RACI-aware supervisor.
    from kotodama.primitives import kaisya_member  # noqa: E402
    kaisya_member.register(worker, timeout_ms=90_000)
    # lawfirm.etzhayyim.com intake + matter creation (closes the missing entry-point
    # gap; smoke test + engagementClose reference vertex_lawfirm_matter).
    from kotodama.primitives import lawfirm_intake  # noqa: E402
    lawfirm_intake.register(worker, timeout_ms=60_000)
    # lawfirm.etzhayyim.com tenant lifecycle — bootstrap / suspend / promote.
    # Backs com.etzhayyim.apps.lawfirm.tenantBootstrap lexicon → BPMN
    # lawfirm_tenant_bootstrap → vertex_lawfirm_tenant + audit + edge.
    from kotodama.primitives import lawfirm_tenant  # noqa: E402
    lawfirm_tenant.register(worker, timeout_ms=60_000)
    # lawfirm.etzhayyim.com billing — Mode A flat / Mode B rev-share Connect
    # subscription + webhook invoice.paid handler. Backs the W11-W12
    # SOW-signed → first-invoice-paid critical path.
    from kotodama.primitives import lawfirm_billing  # noqa: E402
    lawfirm_billing.register(worker, timeout_ms=60_000)
    # lawfirm.etzhayyim.com cadence dispatch — walks vertex_lawfirm_lead.next_action_at
    # daily, fires Tier-2 warm-intro mails per cadence schedule, logs
    # outreach_event + bumps lead.stage='contacted'. Wired to existing
    # lawfirm_sales_cadence_tick BPMN (R/PT24H).
    from kotodama.primitives import lawfirm_cadence_dispatch  # noqa: E402
    lawfirm_cadence_dispatch.register(worker, timeout_ms=90_000)
    # lawfirm.etzhayyim.com reply detection — backs com.etzhayyim.apps.lawfirm.mailReplyWebhook.
    # Inbound mail → match lead by from_email/subject → INSERT outreach_event
    # (event_kind='reply_received', direction='inbound') → suppress follow-up
    # drafts via NOT EXISTS gate in dispatchFollowUps + advance lead.stage.
    from kotodama.primitives import lawfirm_reply_record  # noqa: E402
    lawfirm_reply_record.register(worker, timeout_ms=30_000)
    # warehouse.etzhayyim.com WMS primitives — sku.register, putaway.{planBin,persist},
    # pick.{allocate,persist}, inventory.read. ADR-0036 Hyperdrive direct.
    from kotodama.primitives import warehouse as _warehouse  # noqa: E402
    _warehouse.register(worker, timeout_ms=60_000)
    # yard-ops.etzhayyim.com primitives — slot.allocate, trailer.persist,
    # dockDoor.select, dockJob.{persist,complete}, dockSchedule.read +
    # loadingRobot.mission.dispatch (cross-actor edge to existing
    # loading-robot BPMN executeLoadingMission).
    from kotodama.primitives import yard_ops as _yard_ops  # noqa: E402
    _yard_ops.register(worker, timeout_ms=60_000)

    # coverageGapBridge.bpmn timer-start R/PT6H → minimax-regret scan →
    # gateway routing to the matching task: OFAC SDN ingest, SQL UDF infer,
    # or LangGraph synthesis (business_person_synth_v1 etc.).
    from kotodama.primitives import coverage_gap  # noqa: E402
    coverage_gap.register(worker, timeout_ms=300_000)
    # Vector embedding backfill for actor profiles and posts. The worker
    # writes Phase 1 etzhayyim-mm-768 rows; Zeebe owns batch cadence/retries.
    from kotodama.primitives import vector_embedding  # noqa: E402
    vector_embedding.register(worker, timeout_ms=600_000)
    # GLEIF LEI global company-data ingest planning and normalization.
    from kotodama.primitives import open_lei  # noqa: E402
    open_lei.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # Recursive org unit hierarchy (department / project / committee …) under LEI.
    from kotodama.primitives import org_unit  # noqa: E402
    org_unit.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # Public Malak public-ad-library ingest. Zeebe owns cadence; Python worker
    # queues and processes vertex_ads_* scraper runs directly against RW.
    from kotodama.primitives import public_malak_ads  # noqa: E402
    public_malak_ads.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # malak (cybercrime intel) — registers 25 task_type:
    # 10 existing (registerThreatActor / draftPoliceReport / AgencyReferral / ...)
    # + 15 Phase 0 surveillance + agency-outreach stubs added 2026-05-13
    # (CXO-LEDGER #32-34, formerly mehikari). Stubs return `phase0_stub` until
    # Phase 1 着手 (2026-08-01); 4 hard gates (warrant / two-stage approval /
    # opt-in source / business-hour) enforce defense-in-depth.
    from kotodama.primitives import malak as _malak_primitives  # noqa: E402
    _malak_primitives.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # OS Messaging public LINE/Telegram open-channel ingest. Webhooks stay in
    # the appview; public crawling is handled here as a scheduled worker path.
    from kotodama.primitives import os_messaging_open_channels  # noqa: E402
    os_messaging_open_channels.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)
    # Afghanistan government actor migration. The CF Worker is no longer the
    # app actor runtime for these XRPCs; MCP/BPMN dispatches to this k8s worker.
    from kotodama.primitives import gov_afg  # noqa: E402
    gov_afg.register(worker, timeout_ms=180_000)
    # South Africa government actor migration. Official gov.za sources are
    # queued through site.etzhayyim.com before WET/WAT updates are reflected here.
    from kotodama.primitives import gov_zaf  # noqa: E402
    gov_zaf.register(worker, timeout_ms=180_000)
    # Angola government actor migration. Official governo.gov.ao pages are
    # queued through site.etzhayyim.com before WET/WAT updates are reflected here.
    from kotodama.primitives import gov_ago  # noqa: E402
    gov_ago.register(worker, timeout_ms=180_000)
    # Russia government actor migration. Official government.ru/kremlin.ru pages
    # are queued through site.etzhayyim.com before WET/WAT updates are reflected here.
    from kotodama.primitives import gov_rus  # noqa: E402
    gov_rus.register(worker, timeout_ms=180_000)
    # South Korea government actor migration. Official gov.kr pages are queued
    # through site.etzhayyim.com before WET/WAT updates are reflected here.
    from kotodama.primitives import gov_kor  # noqa: E402
    gov_kor.register(worker, timeout_ms=180_000)
    # North Korea (DPRK) government actor migration.
    from kotodama.primitives import gov_prk  # noqa: E402
    gov_prk.register(worker, timeout_ms=180_000)
    # Hong Kong SAR government actor migration.
    from kotodama.primitives import gov_hkg  # noqa: E402
    gov_hkg.register(worker, timeout_ms=180_000)
    # Wave 2 T2 migration — 133 gov state actors batch-migrated from CF Workers
    # to kotodama LangServer primitives (2026-04-28). Each module exposes 8 task types
    # (seedOrgs, registerDIDs, followSiteDeps, resolveOrgPath, listOrgs,
    # syncWetUpdates, shinka, heartbeatTick) under xrpc.com.etzhayyim.gov{Code}.*.
    from kotodama.primitives import gov_alb  # noqa: E402
    gov_alb.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_and  # noqa: E402
    gov_and.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_are  # noqa: E402
    gov_are.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_arg  # noqa: E402
    gov_arg.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_atg  # noqa: E402
    gov_atg.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_aus  # noqa: E402
    gov_aus.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_aut  # noqa: E402
    gov_aut.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bel  # noqa: E402
    gov_bel.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bgd  # noqa: E402
    gov_bgd.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bgr  # noqa: E402
    gov_bgr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bhr  # noqa: E402
    gov_bhr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bih  # noqa: E402
    gov_bih.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_blr  # noqa: E402
    gov_blr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bol  # noqa: E402
    gov_bol.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bra  # noqa: E402
    gov_bra.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_brb  # noqa: E402
    gov_brb.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_brn  # noqa: E402
    gov_brn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_bwa  # noqa: E402
    gov_bwa.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_can  # noqa: E402
    gov_can.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_che  # noqa: E402
    gov_che.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_chl  # noqa: E402
    gov_chl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_chn  # noqa: E402
    gov_chn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_civ  # noqa: E402
    gov_civ.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_cmr  # noqa: E402
    gov_cmr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_cod  # noqa: E402
    gov_cod.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_col  # noqa: E402
    gov_col.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_cri  # noqa: E402
    gov_cri.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_cub  # noqa: E402
    gov_cub.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_cyp  # noqa: E402
    gov_cyp.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_cze  # noqa: E402
    gov_cze.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_deu  # noqa: E402
    gov_deu.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_dma  # noqa: E402
    gov_dma.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_dnk  # noqa: E402
    gov_dnk.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_dom  # noqa: E402
    gov_dom.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_dza  # noqa: E402
    gov_dza.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ecu  # noqa: E402
    gov_ecu.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_egy  # noqa: E402
    gov_egy.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_esp  # noqa: E402
    gov_esp.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_est  # noqa: E402
    gov_est.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_eth  # noqa: E402
    gov_eth.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_fin  # noqa: E402
    gov_fin.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_fji  # noqa: E402
    gov_fji.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_fra  # noqa: E402
    gov_fra.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_gbr  # noqa: E402
    gov_gbr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_geo  # noqa: E402
    gov_geo.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_gha  # noqa: E402
    gov_gha.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_grc  # noqa: E402
    gov_grc.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_grd  # noqa: E402
    gov_grd.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_gtm  # noqa: E402
    gov_gtm.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_guy  # noqa: E402
    gov_guy.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_hnd  # noqa: E402
    gov_hnd.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_hrv  # noqa: E402
    gov_hrv.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_hti  # noqa: E402
    gov_hti.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_hun  # noqa: E402
    gov_hun.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_idn  # noqa: E402
    gov_idn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ind  # noqa: E402
    gov_ind.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_irl  # noqa: E402
    gov_irl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_irn  # noqa: E402
    gov_irn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_irq  # noqa: E402
    gov_irq.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_isl  # noqa: E402
    gov_isl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ita  # noqa: E402
    gov_ita.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_jam  # noqa: E402
    gov_jam.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_jor  # noqa: E402
    gov_jor.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_jpn  # noqa: E402
    gov_jpn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_kaz  # noqa: E402
    gov_kaz.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ken  # noqa: E402
    gov_ken.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_kgz  # noqa: E402
    gov_kgz.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_khm  # noqa: E402
    gov_khm.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_kwt  # noqa: E402
    gov_kwt.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_lao  # noqa: E402
    gov_lao.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_lbn  # noqa: E402
    gov_lbn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_lby  # noqa: E402
    gov_lby.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_lka  # noqa: E402
    gov_lka.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ltu  # noqa: E402
    gov_ltu.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_lux  # noqa: E402
    gov_lux.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_lva  # noqa: E402
    gov_lva.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mar  # noqa: E402
    gov_mar.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mdg  # noqa: E402
    gov_mdg.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mex  # noqa: E402
    gov_mex.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mhl  # noqa: E402
    gov_mhl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mkd  # noqa: E402
    gov_mkd.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mlt  # noqa: E402
    gov_mlt.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mmr  # noqa: E402
    gov_mmr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mne  # noqa: E402
    gov_mne.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mng  # noqa: E402
    gov_mng.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_moz  # noqa: E402
    gov_moz.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_mys  # noqa: E402
    gov_mys.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_nga  # noqa: E402
    gov_nga.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_nic  # noqa: E402
    gov_nic.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_nld  # noqa: E402
    gov_nld.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_nor  # noqa: E402
    gov_nor.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_npl  # noqa: E402
    gov_npl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_nzl  # noqa: E402
    gov_nzl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_omn  # noqa: E402
    gov_omn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_pak  # noqa: E402
    gov_pak.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_pan  # noqa: E402
    gov_pan.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_per  # noqa: E402
    gov_per.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_phl  # noqa: E402
    gov_phl.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_png  # noqa: E402
    gov_png.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_pol  # noqa: E402
    gov_pol.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_prt  # noqa: E402
    gov_prt.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_pry  # noqa: E402
    gov_pry.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_pse  # noqa: E402
    gov_pse.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_qat  # noqa: E402
    gov_qat.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_rou  # noqa: E402
    gov_rou.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_rwa  # noqa: E402
    gov_rwa.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_sau  # noqa: E402
    gov_sau.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_sdn  # noqa: E402
    gov_sdn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_sen  # noqa: E402
    gov_sen.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_sgp  # noqa: E402
    gov_sgp.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_slv  # noqa: E402
    gov_slv.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_srb  # noqa: E402
    gov_srb.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ssd  # noqa: E402
    gov_ssd.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_sur  # noqa: E402
    gov_sur.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_svk  # noqa: E402
    gov_svk.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_svn  # noqa: E402
    gov_svn.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_swe  # noqa: E402
    gov_swe.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_tha  # noqa: E402
    gov_tha.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_tjk  # noqa: E402
    gov_tjk.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_tkm  # noqa: E402
    gov_tkm.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_tls  # noqa: E402
    gov_tls.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_tur  # noqa: E402
    gov_tur.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_tza  # noqa: E402
    gov_tza.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_uga  # noqa: E402
    gov_uga.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ukr  # noqa: E402
    gov_ukr.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ury  # noqa: E402
    gov_ury.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_usa  # noqa: E402
    gov_usa.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_uzb  # noqa: E402
    gov_uzb.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_ven  # noqa: E402
    gov_ven.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_vnm  # noqa: E402
    gov_vnm.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_yem  # noqa: E402
    gov_yem.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_zmb  # noqa: E402
    gov_zmb.register(worker, timeout_ms=180_000)
    from kotodama.primitives import gov_zwe  # noqa: E402
    gov_zwe.register(worker, timeout_ms=180_000)
    # maps Sentinel L7 ingest + RunPod analysis (ADR-2604271800).
    # Two task types: maps.sentinel.stac.search (R/PT24H ingest) and
    # maps.sentinel.runpod.analyze (XRPC-triggered LangChain + RunPod).
    from kotodama.primitives import maps_sentinel  # noqa: E402
    maps_sentinel.register(worker, timeout_ms=180_000)
    # maps live aircraft tracker — Flightradar24 equivalent (2026-05-01).
    # Two task types: flight.live.poll (R/PT10S OpenSky /states/all) and
    # flight.track.compact (R/PT5M trajectory compaction → vertex_aircraft_track).
    from kotodama.primitives import aircraft_live  # noqa: E402
    aircraft_live.register(worker, timeout_ms=30_000)
    # maps live satellite tracker — N2YO equivalent (2026-05-01).
    # Three task types: satellite.tle.refresh (R/PT6H CelesTrak),
    # satellite.pass.precompute (R/PT1H SGP4 → vertex_satellite_pass),
    # satellite.pass.compute (XRPC-triggered on-demand SGP4).
    from kotodama.primitives import satellite_live  # noqa: E402
    satellite_live.register(worker, timeout_ms=300_000)
    # maps celestial catalog ingest — HYG (~9K naked-eye stars) + OpenNGC
    # (~5K deep-sky / galaxies / nebulae / clusters) for the globe view's
    # accurate star background (R/P30D, com.etzhayyim.apps.maps.ingestCelestialCatalogs).
    from kotodama.primitives import celestial_catalog  # noqa: E402
    celestial_catalog.register(worker, timeout_ms=1_800_000)
    # maps AIS Marine vessel tracking — MarineTraffic-equivalent (ADR-2605011500).
    # Six task types: aismarine.{position.batchInsert, master.upsert,
    # voyage.detectWindow, master.refresh, density.verify, query.bbox}.
    # Long-running aisstream.io WebSocket consumer is the K8s Deployment
    # 50-infra/vultr/bulk-ingest/aismarine-consumer/, not a LangServer task.
    from kotodama.primitives import aismarine  # noqa: E402
    aismarine.register(worker, timeout_ms=60_000)
    # Flight offer ingest + watchlist BPMN tasks (ADR-0056 2026-04-28).
    # 12 task types under flight.offer.* back the 12 flightOffer NSIDs that
    # route through BPMN dispatcher. fetchFromSource / searchOffers / pollWatchlist
    # use 30s / 15s / 300s timeouts respectively; the rest use a 15s default.
    FLIGHT_OFFER_DEFAULT_MS = 15_000
    FLIGHT_OFFER_FETCH_MS = 30_000
    FLIGHT_OFFER_POLL_MS = 300_000
    FLIGHT_OFFER_CLEANUP_MS = 300_000
    from kotodama.ingest.flight_offer import (  # noqa: E402
        task_flight_offer_fetch,
        task_flight_offer_fetch_from_source,
        task_flight_offer_check_drop,
        task_flight_offer_add_watch,
        task_flight_offer_remove_watch,
        task_flight_offer_list_watch,
        task_flight_offer_poll_watchlist,
        task_flight_offer_get_cheapest,
        task_flight_offer_list_sources,
        task_flight_offer_list_airlines,
        task_flight_offer_source_health,
        task_flight_offer_cleanup_runs,
    )
    worker.task(task_type="flight.offer.fetch",            single_value=False, timeout_ms=FLIGHT_OFFER_FETCH_MS)(task_flight_offer_fetch)
    worker.task(task_type="flight.offer.fetchFromSource",  single_value=False, timeout_ms=FLIGHT_OFFER_FETCH_MS)(task_flight_offer_fetch_from_source)
    worker.task(task_type="flight.offer.checkDrop",        single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_check_drop)
    worker.task(task_type="flight.offer.addWatch",         single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_add_watch)
    worker.task(task_type="flight.offer.removeWatch",      single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_remove_watch)
    worker.task(task_type="flight.offer.listWatch",        single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_list_watch)
    worker.task(task_type="flight.offer.pollWatchlist",    single_value=False, timeout_ms=FLIGHT_OFFER_POLL_MS)(task_flight_offer_poll_watchlist)
    worker.task(task_type="flight.offer.getCheapest",      single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_get_cheapest)
    worker.task(task_type="flight.offer.listSources",      single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_list_sources)
    worker.task(task_type="flight.offer.listAirlines",     single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_list_airlines)
    worker.task(task_type="flight.offer.sourceHealth",     single_value=False, timeout_ms=FLIGHT_OFFER_DEFAULT_MS)(task_flight_offer_source_health)
    worker.task(task_type="flight.offer.cleanupRuns",      single_value=False, timeout_ms=FLIGHT_OFFER_CLEANUP_MS)(task_flight_offer_cleanup_runs)

    # curpus2skill resident extraction pass: corpus text -> ESCO skill evidence.
    from kotodama.ingest.curpus2skill import task_curpus2skill_extract_evidence  # noqa: E402
    worker.task(task_type="curpus2skill.extractEvidence", single_value=False, timeout_ms=300_000)(
        task_curpus2skill_extract_evidence
    )

    # maps building 3D model ingest + H3 coverage (R/PT1H BPMN worker).
    # Three task types: maps.building.claimCells, enrichFromOsm, updateCoverage.
    from kotodama.primitives import maps_building_3d  # noqa: E402
    maps_building_3d.register(worker, timeout_ms=180_000)
    # science knowledge graph: paper ingest, element seed, taxon sync (ADR-0056).
    # Seven task types: science.paper.{fetchArxiv,embedBatch,linkGraph},
    #   science.element.{seedElements,seedMaterials},
    #   science.taxon.{syncNcbi,seedVegetation}.
    from kotodama.primitives import science_knowledge  # noqa: E402
    science_knowledge.register(worker, timeout_ms=180_000)
    # IPFS content-addressed archival. Two task types:
    #   ipfs.add      — upload bytes / fetch URL and add to ipfs.etzhayyim.com
    #   ipfs.pinByCid — pin a CID already reachable by the Kubo node
    from kotodama.primitives import ipfs_ingest  # noqa: E402
    ipfs_ingest.register(worker)

    # ADR-2604281400 Phase 2/3 — GCC contribution royalties.
    # Timer/XRPC BPMNs call these handlers for source registration and daily credit().
    from kotodama.primitives import contribution_royalty  # noqa: E402
    contribution_royalty.register(worker, timeout_ms=300_000)

    # ADR-2604301200 — Web4 contract-DID autonomous agent economy.
    # Runtime lease quote/reserve/renew/hibernate and graph-visible income,
    # usage, slash, and child-org lineage records.
    from kotodama.primitives import agent_economy  # noqa: E402
    agent_economy.register(worker, timeout_ms=SHINKA_TIMEOUT_MS)

    # Yukkuri video generation pipeline (ADR-0056 BPMN-as-actor).
    # Six task types backing yukkuriCompose.bpmn:
    #   yukkuri.scene.persist, voice.synthesize, image.generate, video.assemble,
    #   critic.review, social.post.
    from kotodama.primitives import yukkuri  # noqa: E402
    yukkuri.register(worker, timeout_ms=120_000)

    # media-gamers chart analysis pipeline (ADR-0056 BPMN-as-actor).
    # Two task types backing chartFetch.bpmn + chartAnalyze.bpmn:
    #   mediaGamers.chart.fetchAndPersist, mediaGamers.chart.analyze.
    from kotodama.primitives import media_gamers_chart  # noqa: E402
    media_gamers_chart.register(worker, timeout_ms=180_000)

    # Telecom sub-domain primitives (17 domains × 8 tasks each, ADR-0056).
    # These were present in primitives/ but not wired to the worker — dark tasks.
    from kotodama.primitives import (  # noqa: E402
        telecom_5g_security,
        telecom_5gcore,
        telecom_esim,
        telecom_ims,
        telecom_li,
        telecom_mec,
        telecom_nfv,
        telecom_npn,
        telecom_ntn,
        telecom_optical,
        telecom_oran,
        telecom_oss,
        telecom_resource,
        telecom_supplier,
        telecom_tmf,
        telecom_tsn,
        telecom_wlan,
    )
    for _telecom_mod in (
        telecom_5g_security, telecom_5gcore, telecom_esim, telecom_ims,
        telecom_li, telecom_mec, telecom_nfv, telecom_npn, telecom_ntn,
        telecom_optical, telecom_oran, telecom_oss, telecom_resource,
        telecom_supplier, telecom_tmf, telecom_tsn, telecom_wlan,
    ):
        _telecom_mod.register(worker, timeout_ms=60_000)

    # Onion crawl seed + queue tasks (onion.crawl.queueSeeds / processQueue).
    from kotodama.primitives import onion_crawl  # noqa: E402
    onion_crawl.register(worker, timeout_ms=ROBOTICS_TIMEOUT_MS)

    # Intel dependency-graph inference (10 task types: run.create, candidate.scan,
    # owl.validate, langgraph.resolve, edge.materialize, entity.resolve,
    # dependency.list, dependency.explain, graph.counterparty, graph.buildingOwnership).
    from kotodama.primitives import intel  # noqa: E402
    intel.register(worker, timeout_ms=SHINKA_TIMEOUT_MS)

    # APQC/ISIC/ISCO migration primitives. Standalone WASM is retired; these task
    # types provide LangServer + LangGraph + UDF execution surfaces for the same
    # classification/runtime contracts.

    # Hanrei (判例) collection primitives (13 task types: register.courtProfiles,
    # register.jurisdictions, collect.cases/caseDetail/casesBatch/gazette/legislation/
    # egovLaws/wikidataCourts/jurisdictionCases/jurisdictionLegislation/jurisdictionGazette,
    # seed.cases).
    from kotodama.primitives import hanrei  # noqa: E402
    hanrei.register(worker, timeout_ms=180_000)

    # ISIN securities registry primitives (4 task types: collect.usSecurities,
    # collect.jpSecurities, enrich.cik, collect.edinetFiling).
    from kotodama.primitives import isin  # noqa: E402
    isin.register(worker, timeout_ms=180_000)

    # Legal-entity registry primitives (16 task types: GLEIF, EDGAR, and
    # country registry collection surfaces moved out of the thin CF Worker).
    from kotodama.primitives import legal_entity  # noqa: E402
    legal_entity.register(worker, timeout_ms=180_000)

    # Handotai semiconductor intelligence primitives (3 task types: seed.writers,
    # collect.rssAll, generate.digest).
    from kotodama.primitives import handotai  # noqa: E402
    handotai.register(worker, timeout_ms=180_000)

    # JP Fiscal ingest primitives (ADR-0035 T2 migration, 2 task types:
    # jpFiscal.ingest.edinet, jpFiscal.ingest.egovContracts).
    from kotodama.primitives import jp_fiscal  # noqa: E402
    jp_fiscal.register(worker, timeout_ms=180_000)

    # IR scrape primitives (2 task types: irScrape.queueSeeds,
    # irScrape.processQueue). RSS-first, HTML fallback. Feeds intel graph.
    from kotodama.primitives import ir_scrape  # noqa: E402
    ir_scrape.register(worker, timeout_ms=300_000)

    # site.etzhayyim.com IVF+PQ reindex pipeline (4 task types:
    # site.ivfPq.embedMarkdown, site.ivfPq.updateCentroids,
    # site.ivfPq.trainCodebook, site.ivfPq.encodeChunks).
    # Weekly batch via ivfPqReindex.bpmn R/P7D timer. faiss-cpu lazy-imported.
    from kotodama.primitives import site_ivf_pq  # noqa: E402
    site_ivf_pq.register(worker, timeout_ms=3_600_000)

    # site.etzhayyim.com Corpus2Skill distillation (1 task type:
    # site.corpus2skill.distillDomain). Weekly batch via corpus2skillDistill.bpmn.
    from kotodama.primitives import site_corpus_skill  # noqa: E402
    site_corpus_skill.register(worker, timeout_ms=7_200_000)

    # Resource-flow anomaly detection (ADR-0028 + ADR-0046, all 3 flow classes).
    from kotodama.primitives import resource_flow  # noqa: E402
    resource_flow.register(worker, timeout_ms=SHINKA_TIMEOUT_MS)

    # maps3d reconstruction pipeline (maps3d_process_tile BPMN).
    # Requires: MAPILLARY_TOKEN env var; COLMAP_WORKER_URL (default: cluster-internal pod).
    from kotodama.primitives import maps3d as _maps3d  # noqa: E402
    _maps3d.register(worker, timeout_ms=3_600_000)

    # site.commonCrawl.* — existing handlers in ingest/site_common_crawl.py,
    # wired here so BPMN instances don't stall waiting for subscribers.
    from kotodama.ingest.site_common_crawl import (  # noqa: E402
        task_site_cc_create_run,
        task_site_cc_plan,
        task_site_cc_acquire_cursor,
        task_site_cc_run_phase,
        task_site_cc_record_artifacts,
        task_site_cc_verify_visibility,
        task_site_cc_advance_cursor,
        task_site_cc_complete_run,
    )
    worker.task(task_type="site.commonCrawl.createRun",       single_value=False, timeout_ms=60_000)(task_site_cc_create_run)
    worker.task(task_type="site.commonCrawl.plan",            single_value=False, timeout_ms=300_000)(task_site_cc_plan)
    worker.task(task_type="site.commonCrawl.acquireCursor",   single_value=False, timeout_ms=60_000)(task_site_cc_acquire_cursor)
    worker.task(task_type="site.commonCrawl.runPhase",        single_value=False, timeout_ms=21_600_000)(task_site_cc_run_phase)
    worker.task(task_type="site.commonCrawl.recordArtifacts", single_value=False, timeout_ms=60_000)(task_site_cc_record_artifacts)
    worker.task(task_type="site.commonCrawl.verifyVisibility",single_value=False, timeout_ms=60_000)(task_site_cc_verify_visibility)
    worker.task(task_type="site.commonCrawl.advanceCursor",   single_value=False, timeout_ms=60_000)(task_site_cc_advance_cursor)
    worker.task(task_type="site.commonCrawl.completeRun",     single_value=False, timeout_ms=60_000)(task_site_cc_complete_run)

    from kotodama.primitives.owl_reasoner import register_owl_tasks  # noqa: E402
    register_owl_tasks(worker)

    # LLM training data export (training.export.{text,triple}).
    # Exports v_training_text / v_training_triple shards to B2 as gzipped JSONL.
    # Requires: B2_ACCESS_KEY_ID, B2_SECRET_ACCESS_KEY, B2_ENDPOINT env vars.
    from kotodama.primitives import training_export  # noqa: E402
    training_export.register(worker, timeout_ms=600_000)

    # ARIA protocol — external internet signal ingestion + minimax (ADR-2604291800).
    # 8 task types: aria.{attention,request,market.delta,money.flow,emotion,influence}.ingest
    #               aria.minimax.sweep, aria.reverse.topo.replan
    from kotodama.primitives import aria_signal  # noqa: E402
    aria_signal.register(worker, timeout_ms=120_000)

    # ongakuka AI music generation (1 task type: ongakuka.music.generate).
    # Calls murakumo /api/audio/v1/music/generations, uploads WAV to B2
    # etzhayyim-ongakuka, writes vertex_ongakuka_track + vertex_ongakuka_generation.
    from kotodama.primitives import ongakuka  # noqa: E402
    ongakuka.register(worker, timeout_ms=600_000)

    # common-crawl entity extraction (1 task type: commonCrawl.entities.extract).
    # URL-regex fast-path + OpenRouter LLM fallback, writes vertex_repo_record rows.
    from kotodama.primitives import common_crawl  # noqa: E402
    common_crawl.register(worker, timeout_ms=600_000)

    LOG.info("registered tasks: chat, classifyT3, translate, storyboard, "
             "llm.knowledge.{retrieve,langgraphAnswer}, "
             "shinka.{loadAndResolve,compose,writeHeartbeat,emitEvolution,tick}, "
             "generic.{db.select,db.insert,db.bulkInsert,db.delete,"
             "db.purgeFuyouPii,db.purgeEpfoPii,db.purgeEsicPii,db.purgeItr1Pii,db.purgeGstr3bPii,"
             "db.purgeDatacenterAccessPii,db.purgeSeiyakuConfidential,"
             "llm.chat,llm.json,pds.dispatch,http.fetch,tls.probe,audit.emit,"
             "comfyui.call,gyosei.source.link,langgraph.run}, "
             "ind.efiling.submit, "
             "ingest.run.markCompleted, rw.health.probe, houbun.{createRun,egovJpn.plan,acquireCursor,"
             "egovJpn.fetch,writeGraph,verifyVisibility,advanceCursor,completeRun}, "
             "fund.{planSources,fetchRaw,persistArtifact,normalizeManager,"
             "normalizeFund,normalizeLp,normalizeInvestment,enrichEntity,computeReturns,writeGraph,verifyCoverage}, "
             "kakaku.{upsertOffer,ingestOfferFromUrl,compareOffers}, "
             "flight.offer.{fetch,fetchFromSource,checkDrop,addWatch,removeWatch,listWatch,"
             "getCheapest,listSources,listAirlines,sourceHealth,cleanupRuns,pollWatchlist}, "
             "yoro.social.{post,platformPulse,respondToMention,respondToFollow}GraphFallback, "
             "murakumo.fleet.healthCheck, "
             "graph.repo.consumeCommits, "
             "kotoba-kotodama.organizer.run, "
             "pds.writeOutbox.sync, "
             "pds.signingKeys.rotateStale, "
             "pds.mitama.cronTriggers.resync, "
             "pds.heartbeat.run, "
             "pds.discoverCache.warm, "
             "pds.domainCoverage.expand, "
             "vectorEmbedding.backfillBatch, "
             "ingest.run.markCompleted, rw.health.probe, "
             "com.etzhayyim.agent.{plan,gameka.studio,gameka.visualCritic}, "
             "gameka.{codegen.renderKamiApp,avatar.render,build.wasmPack}, "
             "mangaka.{panel.batchRender,balloon.batchOverlay,page.batchCompose,records.batchInsertPages,post.publish}, "
             "loadingRobot.{vision.analyze,plan.load,robot.design,mission.plan}, "
             "robotics.{process.catalog,process.dependencies,workflow.plan,kami.scene.plan,transport.plan,sales.plan,"
             "mission.plan,telemetry.schema,mission.simulate,approval.record,telemetry.ingest,mission.status,"
             "fulfillment.close,ems.company.search,ems.company.profile,ems.supplier.shortlist}, "
             "ma.{salesOrigination.intake,targetScreening.score,investmentAdviser.valuation,"
             "buyerMatching.rank,tradeBroker.negotiate,integration.closeAndHandoff,writeGraph,"
             "outreach.composeDraft,outreach.prepareMailerSend,outreach.sendApproved}, "
             "openLei.gleif.{manifest.plan,bulk.collect,record.normalize,ems.match}, "
             "publicMalak.ads.{queueSeedRuns,processQueue}, "
             "osMessaging.openChannels.{queueSeedRuns,processQueue}, "
             "govAfg.{seedOrgs,registerDIDs,followSiteDeps,resolveOrgPath,listOrgs,"
             "syncWetUpdates,shinka,heartbeatTick}, "
             "govZaf.{seedOrgs,registerDIDs,followSiteDeps,ingestOfficialSources,"
             "resolveOrgPath,listOrgs,syncWetUpdates,shinka,heartbeatTick}, "
             "govAgo.{seedOrgs,registerDIDs,followSiteDeps,ingestOfficialSources,"
             "resolveOrgPath,listOrgs,syncWetUpdates,shinka,heartbeatTick}, "
             "govRus.{seedOrgs,registerDIDs,followSiteDeps,ingestOfficialSources,"
             "resolveOrgPath,listOrgs,syncWetUpdates,shinka,heartbeatTick}, "
             "govKor.{seedOrgs,registerDIDs,followSiteDeps,ingestOfficialSources,"
             "resolveOrgPath,listOrgs,syncWetUpdates,shinka,heartbeatTick}, "
             "govPrk.{seedOrgs,registerDIDs,followSiteDeps,ingestOfficialSources,"
             "resolveOrgPath,listOrgs,syncWetUpdates,shinka,heartbeatTick}, "
             "govHkg.{seedOrgs,registerDIDs,followSiteDeps,ingestOfficialSources,"
             "resolveOrgPath,listOrgs,syncWetUpdates,shinka,heartbeatTick}, "
             "legal.corpus.embedText, "
             "ipfs.{add,pinByCid}, "
             "telecom.{ims,5gcore,esim,5g_security,li,mec,nfv,npn,ntn,optical,oran,oss,resource,supplier,tmf,tsn,wlan} (17 sub-domains × 8 tasks), "
             "onion.crawl.{queueSeeds,processQueue}, "
             "intel.{run.create,candidate.scan,owl.validate,langgraph.resolve,edge.materialize,"
             "entity.resolve,dependency.list,dependency.explain,graph.counterparty,graph.buildingOwnership}, "
             "apqc.{materializeSubprocesses,emitEvent,coverageSnapshot}, "
             "openIsic.{classifyEntity,recordConcordance,flagDualUseIndustry,classifyArmsManufacturing}, "
             "openIsco.{classifyWorker,recordConcordance}, "
             "hanrei.{register.courtProfiles,register.jurisdictions,collect.cases,collect.caseDetail,"
             "collect.casesBatch,collect.gazette,collect.legislation,collect.egovLaws,"
             "collect.wikidataCourts,collect.jurisdictionCases,collect.jurisdictionLegislation,"
             "collect.jurisdictionGazette,seed.cases}, "
             "isin.{collect.usSecurities,collect.jpSecurities,enrich.cik,collect.edinetFiling}, "
             "legalEntity.{gleif.fetchPages,gleif.registerDids,edgar.collectUsa,edgar.ingestSecDisclosure,registry.collect*}, "
             "jpFiscal.{ingest.edinet,ingest.egovContracts}, "
             "openPatent.genericManufacturing.{handoffSeiyaku,queueSeiyakuBatchStart,ackSeiyakuBatchStart,summarizeSeiyakuStartProgress}, "
             "resource-flow.detect.anomaly, "
             "legal.corpus.{embedText,searchDocument,fetchBodyText}, "
             "netintel.{dns.delta,ip.enrich,whois.delta,scan.banner,fingerprint.delta}, "
             "science.paper.{fetchArxiv,embedBatch,linkGraph}, "
             "science.element.{seedElements,seedMaterials}, "
             "science.taxon.{syncNcbi,seedVegetation,seedBiologicalTaxa}, "
             "science.mineral.seedIma, "
             "science.compound.seedPubchem, "
             "science.crystal.seedStructures, "
             "science.protein.seedUniprot, "
             "science.kami.{seedElementInstances,seedVegetationInstances}, "
             "contribution.{registerSource,distributeRoyalties}, "
             "yukkuri.{scene.persist,voice.synthesize,image.generate,video.assemble,critic.review,social.post}, "
             "mediaGamers.chart.{fetchAndPersist,analyze}, "
             "shinshi.{video.render,scene.render,scene.bulkSeed}, "
             "maps3d.{fetchMapillary,curateImages,visionAnnotate,replanReconstruction,colmapTile,simplifyAndExport,linkActor}, "
             "site.commonCrawl.{createRun,plan,acquireCursor,runPhase,recordArtifacts,verifyVisibility,advanceCursor,completeRun}, "
             "patent.{blob.convert,epoOps.fillCitations,usptoPatentsview.ingestPatent,usptoPatentsview.ingestCitation}, "
             "owl.{el.classify,dl.classify,dl.consistency,benchmark.compare,ql.precompute}, "
             "shacl.validate.complex, "
             "training.export.{text,triple}, "
             "irScrape.{queueSeeds,processQueue}, "
             "site.ivfPq.{embedMarkdown,updateCentroids,trainCodebook,encodeChunks}, "
             "site.corpus2skill.{distillDomain}, "
             "aria.{attention,request,market.delta,money.flow,emotion,influence}.ingest, "
             "aria.minimax.sweep, aria.reverse.topo.replan, "
             "ongakuka.music.generate, "
             "commonCrawl.entities.extract")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    work_task = asyncio.create_task(worker.work())
    watchdog_task = asyncio.create_task(_watchdog(channel, stop))
    activation_task = asyncio.create_task(_activation_monitor(stop))
    LOG.info("watchdog armed: ping=20s timeout=10s threshold=3 heartbeat=%s", _HEARTBEAT_PATH)
    LOG.info("activation_monitor armed: poll=60s alert_threshold=300s url=%s", _LANGSERVER_METRICS_URL)
    await stop.wait()
    LOG.info("shutdown requested")
    work_task.cancel()
    watchdog_task.cancel()
    activation_task.cancel()
    for t in (work_task, watchdog_task, activation_task):
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass
    try:
        from kotodama.db_sync import close_sync_pool

        close_sync_pool()
    except Exception:
        pass
    LOG.info("zeebe_worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
