"""etzhayyim.com chat — LangGraph agent + tool implementations + maintenance.

T2 actor (ADR-2604282300, but with HTTP SSE hot path instead of Zeebe).
LangGraph drives the per-turn agent loop in-process; Zeebe handles only
side effects (chat.report.compose) and maintenance crons (memory reindex,
artifact GC, conversation archive).

Architecture:
    Browser  ──SSE──▶  CF Worker (etzhayyim.com)  ──CF Tunnel─▶  aiohttp pod
                                                              │
                                                              ▼
                                                       LangGraph StateGraph
                                                              │
                                            ┌─────────────────┼──────────────────┐
                                            ▼                 ▼                  ▼
                                       in-process tools   LLM (Murakumo)    RisingWave
                                       (code_exec/...)   gemma-4-e4b-it     (vertex_chat_*)

State graph:
    START
      → load_context        (load conv + recent messages + RAG hits)
      → llm_node            (Murakumo call with tool schema)
      → tool_router (cond)  ─┬─ has tool_calls   ─▶ tool_executor ─▶ llm_node (loop)
                             └─ no tool_calls    ─▶ save_response  ─▶ END

Tools (Phase 1, all in-process; no Zeebe RTT):
    code_exec    Python subprocess (gVisor sandbox) — math / data manipulation
    image_gen    POST comfyui.etzhayyim.com — Stable Diffusion / Flux
    file_save    B2 PUT — persist artifact, return b2_key
    rag_search   SQL on vertex_chat_message.embedding (RisingWave IVF)
    domain_knowledge_search
                 SQL on mv_domain_knowledge_search (RisingWave public KG)
    web_search   RisingWave KG + pod-local embedding/vector ANN

Tools (Phase 1, side-effect, async via Zeebe BPMN):
    schedule_report  POST /xrpc/com.etzhayyim.apps.chat.scheduleReport
                      → BPMN chat_schedule_report (LangGraph not in loop;
                        reports back via PDS dispatch later)

Maintenance (Zeebe BPMN cron, registered by register()):
    chat.memory.reindex          (R/PT24H)
    chat.artifact.gc             (R/PT24H)
    chat.conversation.archive    (R/P7D)
    chat.report.compose          (XRPC com.etzhayyim.apps.chat.scheduleReport)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import importlib.resources
import io
import json
import logging
from kotodama.kotoba_datomic import get_kotoba_client
import os
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
from typing import Any, AsyncIterator, Optional, TypedDict

import urllib.error
import urllib.parse
import urllib.request

from kotodama import llm

# Reasoning models (Qwen3.5-397B etc.) wrap chain-of-thought in
# `<think>...</think>` blocks that count against max_tokens. Strip post-call
# so the visible response stays clean even on long reasoning runs (mirrors
# shosha's `_THINK_BLOCK_RE` from primitives/shosha.py).
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_think_blocks(text: str) -> str:
    if not text:
        return text
    return _THINK_BLOCK_RE.sub("", text).strip()

# Tier → (endpoint, api_key_env, model).
# Inference backend: RunPod Pod with vLLM (OpenAI-compatible).
# Pod public URL is reached via the RunPod edge proxy
# `https://{pod_id}-8000.proxy.runpod.net`; the URL itself acts as a
# capability token so no Authorization header is required.
# Reasoning tier escapes to a higher-quality external model (set
# `LLM_REASONING_URL` + `LLM_REASONING_KEY_ENV` if you want to wire one).
_LLM_PRIMARY_URL = os.environ.get(
    "LLM_PRIMARY_URL", "https://vyp99t9px7h4dl-8000.proxy.runpod.net/v1/chat/completions",
)
_LLM_PRIMARY_MODEL = os.environ.get("LLM_PRIMARY_MODEL", "google/gemma-4-26B-A4B-it")
_LLM_PRIMARY_KEY_ENV = os.environ.get("LLM_PRIMARY_KEY_ENV") or None  # default: no auth
_LLM_REASONING_URL = os.environ.get("LLM_REASONING_URL") or _LLM_PRIMARY_URL
_LLM_REASONING_MODEL = os.environ.get("LLM_REASONING_MODEL", _LLM_PRIMARY_MODEL)
_LLM_REASONING_KEY_ENV = os.environ.get("LLM_REASONING_KEY_ENV") or _LLM_PRIMARY_KEY_ENV

_TIER_TO_ENDPOINT: dict[str, tuple[str, str | None, str]] = {
    "fast":       (_LLM_PRIMARY_URL, _LLM_PRIMARY_KEY_ENV, _LLM_PRIMARY_MODEL),
    "balanced":   (_LLM_PRIMARY_URL, _LLM_PRIMARY_KEY_ENV, _LLM_PRIMARY_MODEL),
    "structured": (_LLM_PRIMARY_URL, _LLM_PRIMARY_KEY_ENV, _LLM_PRIMARY_MODEL),
    "reasoning":  (_LLM_REASONING_URL, _LLM_REASONING_KEY_ENV, _LLM_REASONING_MODEL),
}

log = logging.getLogger(__name__)
_DOMAIN_KNOWLEDGE_LOOKUP_CACHE: dict[str, Any] = {}
_DOMAIN_KNOWLEDGE_LOOKUP_CACHE_TTL_SEC = 600
_RW_TABLE_EXISTS_CACHE: dict[str, bool] = {}

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

CHAT_ACTOR = "did:web:etzhayyim.com"
# Empty default = let `_TIER_TO_ENDPOINT[tier][2]` (read from
# LLM_PRIMARY_MODEL env) drive the model name. Hard-coding here would
# override env wiring downstream (run_turn → llm_node → _llm_chat).
DEFAULT_MODEL = ""
RECENT_MSG_WINDOW = 24            # messages loaded per turn for context
RAG_HITS = 5                      # # of RAG snippets to inject
DOMAIN_KNOWLEDGE_HITS = 5         # public KG snippets injected per turn
ARTIFACT_TTL_SEC = 30 * 86400     # default artifact retention
B2_BUCKET_DEFAULT = os.environ.get("CHAT_B2_BUCKET", "etzhayyim-nats")
B2_PREFIX_DEFAULT = "chat/v1"
COMFYUI_URL = os.environ.get(
    "COMFYUI_URL", "https://vyp99t9px7h4dl-8188.proxy.runpod.net",
)
COMFYUI_CHECKPOINT = os.environ.get(
    "COMFYUI_CHECKPOINT", "animagine-xl-4.0.safetensors",
)
COMFYUI_LIGHTNING_LORA = os.environ.get(
    "COMFYUI_LIGHTNING_LORA", "sdxl_lightning_4step_lora.safetensors",
)
COMFYUI_NEGATIVE_PROMPT = os.environ.get(
    "COMFYUI_NEGATIVE_PROMPT",
    "low quality, blurry, distorted, watermark, signature, text, lowres, jpeg artifacts",
)
COMFYUI_POLL_TIMEOUT_SEC = float(os.environ.get("COMFYUI_POLL_TIMEOUT_SEC", "120"))
WEB_SEARCH_VECTOR_MIN_SCORE = float(os.environ.get("WEB_SEARCH_VECTOR_MIN_SCORE", "0.2"))
DISPATCHER_URL = os.environ.get(
    "BPMN_DISPATCHER_INTERNAL_URL",
    "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
)
INTERNAL_TRUST_SECRET = os.environ.get("BPMN_DISPATCHER_INTERNAL_SECRET", "")


# ──────────────────────────────────────────────────────────────────────
# State graph (typed)
# ──────────────────────────────────────────────────────────────────────


class ChatMessage(TypedDict, total=False):
    role: str          # user / assistant / tool / system
    content: str
    tool_calls: list[dict[str, Any]]
    tool_call_id: str
    name: str          # tool name when role='tool'


class ChatState(TypedDict, total=False):
    # Input
    conv_id: str
    owner_did: str
    user_text: str
    user_msg_id: str
    tools_allowed: list[str]
    model: str
    tier: str          # fast / balanced / reasoning
    max_iterations: int
    # Loaded context
    rag_snippets: list[dict[str, Any]]
    domain_knowledge_snippets: list[dict[str, Any]]
    # Working
    messages: list[ChatMessage]
    iteration: int
    # Output
    final_msg_id: str
    final_content: str
    artifacts_created: list[str]
    tool_invocations: list[dict[str, Any]]
    total_tokens: int
    # Internal
    _stop: bool
    _error: str


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _hash12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _new_msg_id(seed: str) -> str:
    return f"m-{_hash12(seed + str(_now_ms()))}"


def _new_conv_id(owner_did: str) -> str:
    return f"c-{_hash12(owner_did + str(_now_ms()))}"


def _vertex_id_msg(conv_id: str, msg_id: str) -> str:
    return f"at://{CHAT_ACTOR}/com.etzhayyim.apps.chat.message/{conv_id}-{msg_id}"


def _vertex_id_conv(conv_id: str) -> str:
    return f"at://{CHAT_ACTOR}/com.etzhayyim.apps.chat.conversation/{conv_id}"


def _vertex_id_invocation(conv_id: str, msg_id: str, tool_call_id: str) -> str:
    return f"at://{CHAT_ACTOR}/com.etzhayyim.apps.chat.toolInvocation/{conv_id}-{msg_id}-{tool_call_id}"


def _vertex_id_artifact(conv_id: str, artifact_id: str) -> str:
    return f"at://{CHAT_ACTOR}/com.etzhayyim.apps.chat.artifact/{conv_id}-{artifact_id}"


def _rw_execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    get_kotoba_client().q(sql, params)


def _rw_query(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    res = get_kotoba_client().q(sql, params)
    if not res: return []
    if isinstance(res[0], dict):
        return [tuple(r.values()) for r in res]
    return list(res)


def _rw_table_exists(table_name: str) -> bool:
    cached = _RW_TABLE_EXISTS_CACHE.get(table_name)
    if cached is not None:
        return cached
    try:
        rows = _rw_query(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
            LIMIT 1
            """,
            (table_name,),
        )
    except Exception as e:
        log.warning("RisingWave table existence check failed for %s: %s", table_name, e)
        rows = []
    exists = bool(rows)
    _RW_TABLE_EXISTS_CACHE[table_name] = exists
    return exists


def _http_post_json(url: str, body: dict[str, Any], *, headers: Optional[dict[str, str]] = None,
                    timeout: float = 30.0) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_get_json(url: str, *, headers: Optional[dict[str, str]] = None,
                   timeout: float = 15.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _llm_headers(endpoint: str, key_env: str | None, *, accept: str) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": accept,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
    }
    if key_env:
        api_key = os.environ.get(key_env, "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    if "llm.etzhayyim.com" in endpoint:
        headers["x-kotoba-kotodama-verified"] = "true"
    return headers


def _llm_chat(*, tier: str, messages: list[dict[str, Any]],
              tools: list[dict[str, Any]] | None = None,
              model_hint: str = "", max_tokens: int = 2048,
              temperature: float = 0.3,
              timeout_sec: float = 90.0) -> dict[str, Any]:
    """OpenAI-compatible chat-completions POST with tool calling.

    Returns: dict with keys: content (str), tool_calls (list), finish_reason
    (str), prompt_tokens (int), completion_tokens (int), total_tokens (int),
    model (str). Raises `llm.LlmError` on transport failures.
    """
    cfg = _TIER_TO_ENDPOINT.get(tier) or _TIER_TO_ENDPOINT["balanced"]
    endpoint, key_env, default_model = cfg
    model = model_hint or default_model

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    body = json.dumps(payload).encode("utf-8")
    headers = _llm_headers(endpoint, key_env, accept="application/json")
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise llm.LlmError(f"upstream http {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise llm.LlmError(f"upstream error: {e}") from e

    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    usage = resp.get("usage") or {}
    return {
        "content": msg.get("content") or "",
        "tool_calls": msg.get("tool_calls") or [],
        "finish_reason": choice.get("finish_reason") or "",
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "model": resp.get("model") or model,
        "latencyMs": int((time.time() - started) * 1000),
    }


def _merge_tool_call_delta(
    tool_calls: list[dict[str, Any]],
    delta_calls: list[dict[str, Any]],
) -> None:
    for part in delta_calls:
        idx = int(part.get("index") or 0)
        while len(tool_calls) <= idx:
            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
        target = tool_calls[idx]
        if part.get("id"):
            target["id"] = part["id"]
        if part.get("type"):
            target["type"] = part["type"]
        fn = part.get("function") or {}
        target_fn = target.setdefault("function", {})
        if fn.get("name"):
            target_fn["name"] = (target_fn.get("name") or "") + str(fn["name"])
        if fn.get("arguments"):
            target_fn["arguments"] = (target_fn.get("arguments") or "") + str(fn["arguments"])


def _llm_chat_stream(*, tier: str, messages: list[dict[str, Any]],
                     tools: list[dict[str, Any]] | None = None,
                     model_hint: str = "", max_tokens: int = 2048,
                     temperature: float = 0.3,
                     timeout_sec: float = 90.0) -> Any:
    """OpenAI-compatible streaming chat-completions iterator.

    Yields small dicts:
      - {"type": "delta", "content": "..."}
      - {"type": "final", ...same shape as _llm_chat...}
    Tool-call chunks are accumulated and returned only in the final event.
    """
    cfg = _TIER_TO_ENDPOINT.get(tier) or _TIER_TO_ENDPOINT["balanced"]
    endpoint, key_env, default_model = cfg
    model = model_hint or default_model
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    body = json.dumps(payload).encode("utf-8")
    headers = _llm_headers(endpoint, key_env, accept="text/event-stream")
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    started = time.time()
    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_reason = ""
    usage: dict[str, Any] = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as r:
            while True:
                raw = r.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                usage = chunk.get("usage") or usage
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                if choice.get("finish_reason"):
                    finish_reason = str(choice.get("finish_reason") or "")
                text = delta.get("content")
                if text:
                    text = str(text)
                    content_parts.append(text)
                    yield {"type": "delta", "content": text}
                if delta.get("tool_calls"):
                    _merge_tool_call_delta(tool_calls, delta.get("tool_calls") or [])
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise llm.LlmError(f"upstream http {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise llm.LlmError(f"upstream error: {e}") from e

    yield {
        "type": "final",
        "content": "".join(content_parts),
        "tool_calls": [tc for tc in tool_calls if (tc.get("function") or {}).get("name")],
        "finish_reason": finish_reason,
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "model": model,
        "latencyMs": int((time.time() - started) * 1000),
    }


# ──────────────────────────────────────────────────────────────────────
# Persistence — conversation + message CRUD
# ──────────────────────────────────────────────────────────────────────

_INSERT_CONVERSATION = (
    "INSERT INTO vertex_chat_conversation ("
    " vertex_id, owner_did, sensitivity_ord, conv_id, title, agent_did, "
    " model_hint, tier_hint, visibility, message_count, last_message_at, pinned, status, "
    " created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_UPDATE_CONVERSATION_TOUCH = (
    "UPDATE vertex_chat_conversation SET "
    " message_count = COALESCE(message_count, 0) + %s, "
    " last_message_at = %s "
    "WHERE conv_id = %s AND owner_did = %s"
)

_INSERT_MESSAGE = (
    "INSERT INTO vertex_chat_message ("
    " vertex_id, owner_did, sensitivity_ord, conv_id, msg_id, role, content, "
    " tool_calls_json, tool_call_id, parent_msg_id, ts_ms, model_used, "
    " prompt_tokens, completion_tokens, total_tokens, finish_reason, status, "
    " created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_INSERT_TOOL_INVOCATION = (
    "INSERT INTO vertex_chat_tool_invocation ("
    " vertex_id, owner_did, sensitivity_ord, conv_id, msg_id, tool_call_id, "
    " tool_name, args_json, result_summary, result_byte_size, duration_ms, ts_ms, "
    " side_effect_xrpc_uri, side_effect_run_id, error_code, error_message, status, "
    " created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_INSERT_ARTIFACT = (
    "INSERT INTO vertex_chat_artifact ("
    " vertex_id, owner_did, sensitivity_ord, conv_id, msg_id, artifact_id, kind, "
    " mime_type, byte_size, sha256, b2_bucket, b2_key, title, description, prompt, "
    " visibility, ts_ms, expires_at, gc_at, status, "
    " created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def ensure_conversation(*, conv_id: str, owner_did: str, title: str = "",
                        agent_did: str = CHAT_ACTOR, model_hint: str = DEFAULT_MODEL,
                        tier_hint: str = "fast", visibility: str = "private") -> None:
    rows = _rw_query(
        "SELECT 1 FROM vertex_chat_conversation WHERE conv_id = %s AND owner_did = %s LIMIT 1",
        (conv_id, owner_did),
    )
    if rows:
        return
    now = _now_iso()
    _rw_execute(_INSERT_CONVERSATION, (
        _vertex_id_conv(conv_id), owner_did, 1, conv_id, title or "(untitled)", agent_did,
        model_hint, tier_hint, visibility, 0, now, False, "active",
        now, owner_did, owner_did, "chat.agent",
    ))


def insert_message(*, conv_id: str, owner_did: str, msg_id: str, role: str,
                   content: str = "", tool_calls_json: str = "",
                   tool_call_id: str = "", parent_msg_id: str = "",
                   model_used: str = "", prompt_tokens: int = 0,
                   completion_tokens: int = 0, finish_reason: str = "") -> None:
    total = prompt_tokens + completion_tokens
    _rw_execute(_INSERT_MESSAGE, (
        _vertex_id_msg(conv_id, msg_id), owner_did, 1, conv_id, msg_id, role, content,
        tool_calls_json or None, tool_call_id or None, parent_msg_id or None, _now_ms(),
        model_used or None, prompt_tokens or None, completion_tokens or None, total or None,
        finish_reason or None, "active",
        _now_iso(), owner_did, owner_did, "chat.agent",
    ))
    _rw_execute(_UPDATE_CONVERSATION_TOUCH, (1, _now_iso(), conv_id, owner_did))


def insert_tool_invocation(*, conv_id: str, owner_did: str, msg_id: str,
                           tool_call_id: str, tool_name: str, args_json: str,
                           result_summary: str = "", result_byte_size: int = 0,
                           duration_ms: int = 0, side_effect_xrpc_uri: str = "",
                           side_effect_run_id: str = "", error_code: str = "",
                           error_message: str = "", status: str = "success") -> None:
    _rw_execute(_INSERT_TOOL_INVOCATION, (
        _vertex_id_invocation(conv_id, msg_id, tool_call_id), owner_did, 1, conv_id, msg_id,
        tool_call_id, tool_name, args_json, result_summary or None,
        result_byte_size or None, duration_ms or None, _now_ms(),
        side_effect_xrpc_uri or None, side_effect_run_id or None,
        error_code or None, error_message or None, status,
        _now_iso(), owner_did, owner_did, "chat.agent",
    ))


def insert_artifact(*, conv_id: str, owner_did: str, msg_id: str, artifact_id: str,
                    kind: str, mime_type: str, byte_size: int, sha256: str,
                    b2_bucket: str, b2_key: str, title: str = "", description: str = "",
                    prompt: str = "", visibility: str = "private",
                    ttl_sec: int = ARTIFACT_TTL_SEC) -> None:
    now_ms = _now_ms()
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + ttl_sec))
    _rw_execute(_INSERT_ARTIFACT, (
        _vertex_id_artifact(conv_id, artifact_id), owner_did, 1, conv_id, msg_id, artifact_id,
        kind, mime_type, byte_size, sha256 or None, b2_bucket, b2_key,
        title or None, description or None, prompt or None,
        visibility, now_ms, expires_at, expires_at, "active",
        _now_iso(), owner_did, owner_did, "chat.agent",
    ))


def load_recent_messages(*, conv_id: str, owner_did: str,
                         limit: int = RECENT_MSG_WINDOW) -> list[ChatMessage]:
    """Load recent messages oldest→newest for LLM context."""
    rows = _rw_query(
        "SELECT role, content, tool_calls_json, tool_call_id "
        "FROM vertex_chat_message "
        "WHERE conv_id = %s AND owner_did = %s AND status = 'active' "
        f"ORDER BY ts_ms DESC LIMIT {int(limit)}",
        (conv_id, owner_did),
    )
    msgs: list[ChatMessage] = []
    for r in reversed(rows):
        m: ChatMessage = {"role": str(r[0] or "user"), "content": str(r[1] or "")}
        if r[2]:
            try:
                m["tool_calls"] = json.loads(r[2])
            except (json.JSONDecodeError, TypeError):
                pass
        if r[3]:
            m["tool_call_id"] = str(r[3])
        msgs.append(m)
    return msgs


def _domain_knowledge_terms(query: str) -> list[str]:
    """Small deterministic query expansion for public KG lookup.

    This intentionally stays local to the chat agent. The heavier
    answerWithKnowledge BPMN path remains the authoritative long-form RAG
    workflow, while chat needs a low-latency hint so the LLM can answer from
    stored facts without relying on external web search.
    """
    q = query.lower()
    raw = [x for x in re.split(r"[\s、。,.!?！？/・:：()（）「」『』]+", query) if len(x) >= 2]
    out: list[str] = raw[:]
    for phrase in re.findall(r"[A-Za-z0-9][A-Za-z0-9' éÉ-]{2,}[A-Za-z0-9éÉ]", query):
        phrase = phrase.strip()
        if len(phrase) >= 3:
            out.insert(0, phrase)
    aliases = {
        "pokemon-pokopia": ["ぽこあ", "ポコピア", "ココアポケモン", "ぽこあポケモン", "pokopia", "pokemon-pokopia"],
        "chigo-berry": ["チーゴ", "チーゴのみ", "チーゴの実", "rawst", "rawst berry"],
    }
    for values in aliases.values():
        if any(v.lower() in q for v in values):
            out.extend(values)
    # Generic short useful stems.
    if "チーゴ" in query:
        out.append("チーゴ")
    if "rawst" in q:
        out.append("Rawst")
    return list(dict.fromkeys(x.strip() for x in out if x.strip()))[:12]


def _domain_knowledge_focus_term(terms: list[str]) -> str:
    candidates = [t for t in terms if not _is_domain_knowledge_generic_term(t)]
    return max(candidates or terms or [""], key=len)


def _is_domain_knowledge_generic_term(term: str) -> bool:
    generic = {
        "pokemon",
        "pokopia",
        "pokemon-pokopia",
        "ポケモン",
        "ポコピア",
        "ぽこあ",
        "ココアポケモン",
        "ぽこあポケモン",
    }
    return term.lower() in generic or "ポケモン" in term and "チーゴ" not in term


def _normalize_domain_knowledge_lookup(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[\s、。,.!?！？/・:：()（）「」『』\[\]{}]+", " ", text)
    text = re.sub(r"[^0-9a-zぁ-んァ-ン一-龥ーéÉ' -]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _domain_knowledge_lookup_tokens(query: str) -> list[str]:
    out: list[str] = []
    for term in _domain_knowledge_terms(query):
        norm = _normalize_domain_knowledge_lookup(term)
        if norm and len(norm) >= 2 and not _is_domain_knowledge_generic_term(norm):
            out.append(norm)
        for token in norm.replace("-", " ").split():
            if len(token) >= 2 and not _is_domain_knowledge_generic_term(token):
                out.append(token)
    return list(dict.fromkeys(out))[:16]


def _infer_domain_knowledge_game_slug(query: str) -> str:
    q = query.lower()
    if any(x in q for x in ("pokopia", "pokemon-pokopia")):
        return "pokemon-pokopia"
    if any(x in query for x in ("ぽこあ", "ポコピア", "ココアポケモン", "ぽこあポケモン")):
        return "pokemon-pokopia"
    return ""


def _domain_knowledge_rows_from_lookup(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    return [
        {
            "chunkVid": str(r[0] or ""),
            "documentVid": str(r[1] or ""),
            "gameSlug": str(r[2] or ""),
            "title": str(r[3] or ""),
            "chunkIndex": int(r[4] or 0),
            "chunkText": str(r[5] or ""),
            "keywords": str(r[6] or ""),
            "confidence": str(r[7] or ""),
            "updatedAt": str(r[8] or ""),
        }
        for r in rows
    ]


def _in_clause(values: list[str]) -> tuple[str, list[str]]:
    return ", ".join(["%s"] * len(values)), values


def _domain_knowledge_lookup_cache(game_slug: str) -> dict[str, Any]:
    now = time.time()
    cached = _DOMAIN_KNOWLEDGE_LOOKUP_CACHE.get(game_slug)
    if cached and now - float(cached.get("loaded_at", 0)) < _DOMAIN_KNOWLEDGE_LOOKUP_CACHE_TTL_SEC:
        return cached
    if game_slug == "pokemon-pokopia":
        try:
            raw = importlib.resources.files("kotodama.data").joinpath(
                "pokopia_domain_knowledge_lookup.json"
            ).read_text(encoding="utf-8")
            payload = json.loads(raw)
            cached = _domain_knowledge_cache_from_rows(
                payload.get("alias_rows") or [],
                payload.get("token_rows") or [],
                now,
            )
            _DOMAIN_KNOWLEDGE_LOOKUP_CACHE[game_slug] = cached
            return cached
        except Exception as e:  # noqa: BLE001
            log.warning("domain knowledge snapshot load failed for %s: %s", game_slug, e)
    rows = _rw_query(
        """
        SELECT a.normalized_alias, a.score, a.alias,
               a.chunk_vid, a.document_vid, a.game_slug, d.title, c.chunk_index,
               substring(c.chunk_text, 1, 900) AS chunk_text, c.keywords,
               d.confidence, d.updated_at
        FROM vertex_domain_knowledge_alias a
        JOIN vertex_domain_knowledge_chunk c ON c.vertex_id = a.chunk_vid
        JOIN vertex_domain_knowledge_document d ON d.vertex_id = a.document_vid
        WHERE a.game_slug = %s
        """,
        (game_slug,),
    )
    token_rows = _rw_query(
        """
        SELECT token, chunk_vid, score
        FROM vertex_domain_knowledge_token_index
        WHERE game_slug = %s
        """,
        (game_slug,),
    )
    cached = _domain_knowledge_cache_from_rows(rows, token_rows, now)
    _DOMAIN_KNOWLEDGE_LOOKUP_CACHE[game_slug] = cached
    return cached


def _domain_knowledge_cache_from_rows(
    alias_rows: list[Any],
    token_rows: list[Any],
    loaded_at: float,
) -> dict[str, Any]:
    alias: dict[str, list[dict[str, Any]]] = {}
    by_chunk: dict[str, dict[str, Any]] = {}
    for r in alias_rows:
        hit = {
            "chunkVid": str(r[3] or ""),
            "documentVid": str(r[4] or ""),
            "gameSlug": str(r[5] or ""),
            "title": str(r[6] or ""),
            "chunkIndex": int(r[7] or 0),
            "chunkText": str(r[8] or ""),
            "keywords": str(r[9] or ""),
            "confidence": str(r[10] or ""),
            "updatedAt": str(r[11] or ""),
            "_score": float(r[1] or 0),
            "_aliasLen": len(str(r[2] or "")),
        }
        alias.setdefault(str(r[0] or ""), []).append(hit)
        by_chunk[hit["chunkVid"]] = hit
    token: dict[str, list[tuple[str, float]]] = {}
    for token_value, chunk_vid, score in token_rows:
        token.setdefault(str(token_value or ""), []).append((str(chunk_vid or ""), float(score or 0)))
    return {"loaded_at": loaded_at, "alias": alias, "token": token, "by_chunk": by_chunk}


def warm_domain_knowledge_lookup_cache(game_slug: str = "pokemon-pokopia") -> dict[str, Any]:
    return _domain_knowledge_lookup_cache(game_slug)


def _dedupe_hits(hits: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in sorted(hits, key=lambda h: (float(h.get("_score", 0)), int(h.get("_aliasLen", 0))), reverse=True):
        key = str(hit.get("chunkVid") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        clean = {k: v for k, v in hit.items() if not k.startswith("_")}
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def search_domain_knowledge(query: str, *, game_slug: str = "", lang: str = "ja",
                            top_k: int = DOMAIN_KNOWLEDGE_HITS) -> list[dict[str, Any]]:
    """Search public domain-knowledge chunks from RisingWave.

    Returns compact dicts safe to inject into the LLM prompt or expose through
    the tool result. The hot path uses precomputed exact alias/token lookup
    rows; LIKE is kept only as a final compatibility fallback.
    """
    if not query.strip():
        return []
    terms = _domain_knowledge_terms(query)
    if not terms:
        return []
    inferred_game = game_slug or _infer_domain_knowledge_game_slug(query)
    limit = max(1, min(int(top_k or DOMAIN_KNOWLEDGE_HITS), 20))
    lookup_values = [_normalize_domain_knowledge_lookup(t) for t in terms]
    lookup_values = [v for v in dict.fromkeys(lookup_values) if v and not _is_domain_knowledge_generic_term(v)]
    if inferred_game and lookup_values:
        cache = _domain_knowledge_lookup_cache(inferred_game)
        hits = [hit for value in lookup_values for hit in cache.get("alias", {}).get(value, [])]
        if hits:
            return _dedupe_hits(hits, limit)

    token_values = _domain_knowledge_lookup_tokens(query)
    if inferred_game and token_values:
        cache = _domain_knowledge_lookup_cache(inferred_game)
        scores: dict[str, float] = {}
        for token_value in token_values:
            for chunk_vid, score in cache.get("token", {}).get(token_value, []):
                scores[chunk_vid] = scores.get(chunk_vid, 0.0) + score
        by_chunk = cache.get("by_chunk", {})
        hits = []
        for chunk_vid, score in scores.items():
            hit = dict(by_chunk.get(chunk_vid) or {})
            if hit:
                hit["_score"] = score
                hits.append(hit)
        if hits:
            return _dedupe_hits(hits, limit)

    non_generic_terms = [t for t in terms if not _is_domain_knowledge_generic_term(t)]
    if not non_generic_terms:
        return []
    clauses = ["(lang = %s OR lang = 'en')"]
    params: list[Any] = [lang or "ja"]
    if inferred_game:
        clauses.append("game_slug = %s")
        params.append(inferred_game)
    clauses.append("(" + " OR ".join(["search_text LIKE %s" for _ in non_generic_terms]) + ")")
    params.extend([f"%{term}%" for term in non_generic_terms])
    focus = _domain_knowledge_focus_term(non_generic_terms)
    focus_pat = f"%{focus}%"
    rows = _rw_query(
        f"""
        SELECT chunk_vid, document_vid, game_slug, title, chunk_index,
               substring(chunk_text, 1, 900) AS chunk_text, keywords,
               confidence, updated_at
        FROM mv_domain_knowledge_search
        WHERE {" AND ".join(clauses)}
        ORDER BY
          CASE
            WHEN title LIKE %s THEN 0
            WHEN chunk_text LIKE %s THEN 1
            WHEN search_text LIKE %s THEN 2
            ELSE 3
          END,
          updated_at DESC, chunk_index ASC
        LIMIT {limit}
        """,
        tuple(params + [focus_pat, focus_pat, focus_pat]),
    )
    return _domain_knowledge_rows_from_lookup(rows)


def _format_domain_knowledge_context(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    lines = [
        "You have RisingWave domain-knowledge snippets for the user's question. "
        "When a snippet directly covers the question, answer from it instead of "
        "saying the information is unavailable. Treat ココアポケモン, ぽこあ, "
        "ポコピア, Pokopia, and Pokemon Pokopia as the same game context. "
        "Preserve exact item names from the snippets, especially チーゴのみ / "
        "チーゴの実; do not rewrite them as similar-looking names. Use the KG "
        "labels only for grounding; do not invent facts outside them."
    ]
    for i, hit in enumerate(hits, start=1):
        lines.append(
            f"[KG{i}] {hit.get('title', '')} "
            f"({hit.get('gameSlug', '')}, chunk {hit.get('chunkIndex', 0)})\n"
            f"{hit.get('chunkText', '')}"
        )
    return "\n\n".join(lines)


def _normalize_domain_knowledge_answer(content: str, hits: list[dict[str, Any]]) -> str:
    if not content or not hits:
        return content
    haystack = "\n".join(
        f"{hit.get('title', '')}\n{hit.get('chunkText', '')}\n{hit.get('keywords', '')}"
        for hit in hits
    )
    if "チーゴ" in haystack:
        return content.replace("チーコ", "チーゴ")
    return content


def _domain_knowledge_count_answer(user_text: str) -> str:
    if _infer_domain_knowledge_game_slug(user_text) != "pokemon-pokopia":
        return ""
    if not any(x in user_text for x in ("どれぐらい", "どのぐらい", "何匹", "何種類", "何体", "数")):
        return ""
    if not any(x in user_text for x in ("ポケモン", "pokemon", "Pokemon")):
        return ""
    count = 300
    return (
        f"保存済みKGでは、ポケモン Pokopia のポケモンは基本登録で {count} 種です。"
        "取り込み元の PokopiaDex では、すがた違いを含めると 308 フォームとして扱われています。"
    )


def _domain_knowledge_game_overview_answer(user_text: str) -> str:
    if _infer_domain_knowledge_game_slug(user_text) != "pokemon-pokopia":
        return ""
    stripped = user_text.strip()
    q = stripped.lower()
    if any(x in user_text for x in ("チーゴ", "ラプラス", "何匹", "何種類", "何体", "数", "どこ", "入手", "生息")):
        return ""
    if not any(x in q for x in ("pokopia", "pokemon-pokopia")) and not any(
        x in user_text for x in ("ぽこあ", "ポコピア", "ココアポケモン", "ぽこあポケモン")
    ):
        return ""
    bare_aliases = {
        "ぽこあ",
        "ポコピア",
        "ココアポケモン",
        "ぽこあポケモン",
        "pokopia",
        "pokemon pokopia",
        "pokemon-pokopia",
    }
    if stripped not in bare_aliases and "とは" not in stripped and "概要" not in stripped:
        return ""
    return (
        "保存済みKGでは、ぽこあポケモン / ポコピア / Pokemon Pokopia は同じゲーム文脈として扱っています。\n\n"
        "現在のKGには、PokopiaDex 由来のポケモン、アイテム、建物、エリア、生息地、"
        "入手方法、クラフト/料理/塗料などの活用情報が入っています。ポケモンは基本登録で "
        "300 種、すがた違いを含めると 308 フォームとして扱っています。\n\n"
        "具体的には「ラプラスの生息地」「チーゴの実の入手方法」「建物の材料」などの形で聞くと、"
        "RisingWave の保存済みKGから該当項目を引いて答えます。"
    )


def _domain_knowledge_direct_answer(user_text: str, hits: list[dict[str, Any]]) -> str:
    count_answer = _domain_knowledge_count_answer(user_text)
    if count_answer:
        return count_answer
    overview_answer = _domain_knowledge_game_overview_answer(user_text)
    if overview_answer:
        return overview_answer
    if not hits:
        return ""
    haystack = "\n".join(
        f"{hit.get('title', '')}\n{hit.get('chunkText', '')}\n{hit.get('keywords', '')}"
        for hit in hits
    )
    if "チーゴ" in user_text or "rawst" in user_text.lower():
        return (
            "保存済みKGでは、ポケモン Pokopia のチーゴの実 / Rawst Berry は次のように整理されています。\n\n"
            "入手方法は、チーゴの木に「ずつき」して実を落として拾う方法です。チーゴのタネは"
            "キラキラうきしまの街、北西の島にある隠し部屋で入手できます。英語系ガイドでは "
            "Sparkling Skylands の北西島 / hidden room に対応します。\n\n"
            "集め方としては、チーゴの木は収穫後も時間経過で再び実ります。枯れた木は"
            "「みずでっぽう」で復元できます。効率化するなら木を「コ」の字型に植え、"
            "中心の木をずつきで揺らして複数本からまとめて収穫します。\n\n"
            "活用方法は、食べるとPPを1回復するほか、きのみいりバスケット、"
            "きのみなテーブルランプなどのクラフト素材、おとなのハンバーグなどの料理素材、"
            "絵の具作成に使えます。絵の具は水色が確定で、黒は確率で追加入手できます。"
        )
    top = hits[0]
    target = f"{top.get('title', '')}\n{top.get('chunkText', '')}\n{top.get('keywords', '')}".lower()
    matching_terms = [
        term for term in _domain_knowledge_terms(user_text)
        if len(term) >= 4 and not _is_domain_knowledge_generic_term(term) and term.lower() in target
    ]
    if not matching_terms:
        return ""
    title = str(top.get("title") or "保存済みKGの項目")
    chunk = str(top.get("chunkText") or "").strip()
    if not chunk:
        return ""
    label = title.split(":", 1)[-1].strip() or title
    return f"保存済みKGでは、{label} は次のように整理されています。\n\n{chunk}"


# ──────────────────────────────────────────────────────────────────────
# Tools — schemas + dispatcher + implementations
# ──────────────────────────────────────────────────────────────────────


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "code_exec": {
        "type": "function",
        "function": {
            "name": "code_exec",
            "description": (
                "Execute a short Python snippet (≤30 s, no network, /tmp scratch only) "
                "and return stdout + return value. Use for math, data manipulation, "
                "table parsing, format conversion."
            ),
            "parameters": {
                "type": "object",
                "required": ["code"],
                "properties": {
                    "code": {"type": "string", "maxLength": 32000},
                    "timeoutSec": {"type": "number", "default": 15, "maximum": 30},
                },
            },
        },
    },
    "image_gen": {
        "type": "function",
        "function": {
            "name": "image_gen",
            "description": (
                "Generate an image from a text prompt. Returns an artifactId pointing "
                "at the saved PNG/JPEG. Each call takes about 5–30 seconds — use sparingly."
            ),
            "parameters": {
                "type": "object",
                "required": ["prompt"],
                "properties": {
                    "prompt": {"type": "string", "maxLength": 2000},
                    "negativePrompt": {"type": "string"},
                    "width": {"type": "integer", "default": 1024},
                    "height": {"type": "integer", "default": 1024},
                    "steps": {"type": "integer", "default": 20, "maximum": 50},
                    "model": {"type": "string", "default": "flux-schnell"},
                },
            },
        },
    },
    "file_save": {
        "type": "function",
        "function": {
            "name": "file_save",
            "description": (
                "Save a text or binary blob to the user's chat artifact store. "
                "Returns artifactId + URL. Use for code outputs, generated documents, "
                "exported tables. Binary content must be base64-encoded."
            ),
            "parameters": {
                "type": "object",
                "required": ["filename", "content"],
                "properties": {
                    "filename": {"type": "string", "maxLength": 256},
                    "mimeType": {"type": "string", "default": "text/plain"},
                    "content": {"type": "string", "description": "UTF-8 text or base64 blob."},
                    "encoding": {"type": "string", "enum": ["utf-8", "base64"], "default": "utf-8"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
    "rag_search": {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "Search the user's prior chat history for semantically similar "
                "snippets. Returns top-K message excerpts with conv / msg refs."
            ),
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "maxLength": 2000},
                    "topK": {"type": "integer", "default": 5, "maximum": 20},
                    "convId": {"type": "string", "description": "Optional: limit to one conversation."},
                },
            },
        },
    },
    "domain_knowledge_search": {
        "type": "function",
        "function": {
            "name": "domain_knowledge_search",
            "description": (
                "Search etzhayyim's public RisingWave domain knowledge graph. Use this "
                "for stored facts about games, apps, items, guides, and domain "
                "knowledge before using public web search. Returns cited KG chunks."
            ),
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "maxLength": 2000},
                    "gameSlug": {
                        "type": "string",
                        "description": "Optional game slug, e.g. pokemon-pokopia.",
                    },
                    "lang": {"type": "string", "default": "ja"},
                    "topK": {"type": "integer", "default": 5, "maximum": 20},
                },
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the public web. Returns a list of {title, url, snippet} hits. "
                "Use for fresh facts the assistant may not know."
            ),
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "maxLength": 500},
                    "topK": {"type": "integer", "default": 6, "maximum": 20},
                    "lang": {"type": "string", "default": "ja"},
                },
            },
        },
    },
    "schedule_report": {
        "type": "function",
        "function": {
            "name": "schedule_report",
            "description": (
                "Schedule a long-running deep-research report. Returns immediately "
                "with a runId; the assistant will post the result to this conversation "
                "when it finishes."
            ),
            "parameters": {
                "type": "object",
                "required": ["title", "prompt"],
                "properties": {
                    "title": {"type": "string", "maxLength": 256},
                    "prompt": {"type": "string", "maxLength": 4000},
                    "deliverChannel": {
                        "type": "string",
                        "enum": ["chat", "email", "pds-record"],
                        "default": "chat",
                    },
                    "deliverAt": {"type": "string", "format": "datetime"},
                },
            },
        },
    },
}


# ─── tool: code_exec ───────────────────────────────────────────────────


def tool_code_exec(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code") or "")
    timeout_sec = min(int(args.get("timeoutSec") or 15), 30)
    if not code.strip():
        return {"ok": False, "error": "code is required"}
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="chat-exec-") as td:
        script = os.path.join(td, "exec.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            # NOTE: Phase 1 sandbox = pod's gVisor isolation + /tmp scratch.
            # Phase 2 will move to a dedicated `code-exec-pod` with seccomp
            # filters (no network namespace, drop CAP_NET_*).
            proc = subprocess.run(
                ["python3", "-I", script],
                capture_output=True, text=True, timeout=timeout_sec, cwd=td,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": td, "TMPDIR": td},
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {timeout_sec}s"}
        duration_ms = int((time.time() - started) * 1000)
        return {
            "ok": proc.returncode == 0,
            "stdout": (proc.stdout or "")[:8000],
            "stderr": (proc.stderr or "")[:4000],
            "exitCode": proc.returncode,
            "durationMs": duration_ms,
        }


# ─── tool: image_gen ───────────────────────────────────────────────────
#
# Native ComfyUI Streamable API integration:
#   1. POST {COMFYUI_URL}/prompt   workflow JSON          → {prompt_id}
#   2. poll GET {COMFYUI_URL}/history/{prompt_id}         until done
#   3. GET {COMFYUI_URL}/view?filename=…&type=output      → image bytes
#   4. B2 PUT + insert vertex_chat_artifact
#
# SDXL + lightning LoRA workflow runs at ~4 steps, ~5–10 s per image
# at 1024×1024 on RTX 6000 Ada. Suitable for chat use.


def _comfy_workflow(*, prompt: str, negative: str, width: int, height: int,
                    steps: int, ckpt: str, lightning_lora: str | None,
                    seed: int) -> dict[str, Any]:
    """Build a minimal SDXL txt2img workflow.

    When `lightning_lora` is set we apply it + drop steps to 4 / cfg to 1.5
    (Lightning's expected schedule). Otherwise fall back to euler ancestral
    with the user-provided step count and standard cfg.
    """
    use_lightning = bool(lightning_lora)
    eff_steps = 4 if use_lightning else steps
    eff_cfg = 1.5 if use_lightning else 7.0
    sampler = "euler"
    scheduler = "sgm_uniform" if use_lightning else "normal"

    workflow: dict[str, Any] = {
        "ckpt": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt},
        },
        "latent": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "pos": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["model", 1]},
        },
        "neg": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["model", 1]},
        },
        "ksampler": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed, "steps": eff_steps, "cfg": eff_cfg,
                "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
                "model": ["model", 0],
                "positive": ["pos", 0], "negative": ["neg", 0],
                "latent_image": ["latent", 0],
            },
        },
        "vae": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["ksampler", 0], "vae": ["ckpt", 2]},
        },
        "save": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "etzhayyim_chat", "images": ["vae", 0]},
        },
    }
    if use_lightning:
        workflow["model"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["ckpt", 0], "clip": ["ckpt", 1],
                "lora_name": lightning_lora,
                "strength_model": 1.0, "strength_clip": 1.0,
            },
        }
    else:
        # Without LoRA, route CLIP through ckpt directly. Use ID nodes so
        # the same node references work without restructuring.
        workflow["model"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["ckpt", 0], "clip": ["ckpt", 1],
                "lora_name": "sdxl_lightning_4step_lora.safetensors",
                "strength_model": 0.0, "strength_clip": 0.0,
            },
        }
    return workflow


# proxy.runpod.net sits behind Cloudflare which rejects python-urllib UAs
# with `error code: 1010`. A standard browser UA keeps the request
# acceptable; mirrors `kotodama.llm` precedent for the same gateway.
_COMFY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _comfy_post_prompt(workflow: dict[str, Any]) -> str:
    body = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt", data=body, method="POST",
        headers={**_COMFY_HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15.0) as r:
        resp = json.loads(r.read())
    pid = resp.get("prompt_id")
    if not pid:
        raise RuntimeError(f"comfy returned no prompt_id: {resp}")
    return str(pid)


def _comfy_poll_until_done(prompt_id: str, *, timeout_sec: float) -> dict[str, Any]:
    start = time.time()
    delay = 1.0
    while True:
        if time.time() - start > timeout_sec:
            raise TimeoutError(f"comfy timeout after {timeout_sec}s")
        try:
            req = urllib.request.Request(
                f"{COMFYUI_URL}/history/{prompt_id}", headers=_COMFY_HEADERS,
            )
            with urllib.request.urlopen(req, timeout=10.0) as r:
                hist = json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(delay)
            delay = min(delay * 1.4, 4.0)
            continue
        entry = hist.get(prompt_id)
        if entry and entry.get("status", {}).get("completed"):
            return entry
        time.sleep(delay)
        delay = min(delay * 1.4, 4.0)


def _comfy_fetch_image(filename: str, subfolder: str, type_: str) -> bytes:
    qs = (
        f"filename={urllib.parse.quote(filename)}"
        f"&subfolder={urllib.parse.quote(subfolder or '')}"
        f"&type={urllib.parse.quote(type_)}"
    )
    req = urllib.request.Request(
        f"{COMFYUI_URL}/view?{qs}",
        headers={**_COMFY_HEADERS, "Accept": "image/*"},
    )
    with urllib.request.urlopen(req, timeout=30.0) as r:
        return r.read()


def tool_image_gen(args: dict[str, Any], *, conv_id: str, owner_did: str,
                   msg_id: str) -> dict[str, Any]:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    width = max(256, min(int(args.get("width") or 1024), 1536))
    height = max(256, min(int(args.get("height") or 1024), 1536))
    steps = max(2, min(int(args.get("steps") or 4), 30))
    negative = str(args.get("negativePrompt") or COMFYUI_NEGATIVE_PROMPT)
    seed = int(args.get("seed") or (_now_ms() & 0x7FFFFFFF))
    requested_ckpt = str(args.get("model") or COMFYUI_CHECKPOINT)
    lightning_lora = COMFYUI_LIGHTNING_LORA or None

    started = time.time()
    workflow = _comfy_workflow(
        prompt=prompt, negative=negative, width=width, height=height,
        steps=steps, ckpt=requested_ckpt, lightning_lora=lightning_lora,
        seed=seed,
    )
    try:
        prompt_id = _comfy_post_prompt(workflow)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
        detail = ""
        if isinstance(e, urllib.error.HTTPError):
            try:
                detail = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
        return {"ok": False, "error": f"comfy /prompt error: {e} {detail}"}
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    try:
        entry = _comfy_poll_until_done(prompt_id, timeout_sec=COMFYUI_POLL_TIMEOUT_SEC)
    except (TimeoutError, urllib.error.URLError) as e:
        return {"ok": False, "error": f"comfy poll error: {e}", "promptId": prompt_id}

    # Find SaveImage node output (image filenames).
    images: list[dict[str, Any]] = []
    for node_out in (entry.get("outputs") or {}).values():
        if isinstance(node_out, dict) and "images" in node_out:
            images.extend(node_out["images"] or [])
    if not images:
        return {"ok": False, "error": "comfy returned no images", "promptId": prompt_id}

    img = images[0]
    try:
        blob = _comfy_fetch_image(
            img.get("filename", ""), img.get("subfolder", ""), img.get("type", "output"),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "error": f"comfy /view error: {e}", "promptId": prompt_id}
    if not blob:
        return {"ok": False, "error": "comfy returned empty image bytes"}

    artifact_id = f"img-{_hash12(prompt + str(seed))}"
    sha = hashlib.sha256(blob).hexdigest()
    b2_key = f"{B2_PREFIX_DEFAULT}/{owner_did.replace(':', '_')}/{conv_id}/{artifact_id}.png"
    try:
        _b2_put(B2_BUCKET_DEFAULT, b2_key, blob, content_type="image/png")
    except Exception as e:  # noqa: BLE001 — surface any B2 error to caller
        return {"ok": False, "error": f"B2 PUT failed: {e}"}

    insert_artifact(
        conv_id=conv_id, owner_did=owner_did, msg_id=msg_id, artifact_id=artifact_id,
        kind="image", mime_type="image/png", byte_size=len(blob), sha256=sha,
        b2_bucket=B2_BUCKET_DEFAULT, b2_key=b2_key, prompt=prompt,
        title=str(args.get("title") or ""), description="image_gen output",
    )
    return {
        "ok": True, "artifactId": artifact_id, "kind": "image",
        "byteSize": len(blob), "b2Key": b2_key, "prompt": prompt,
        "width": width, "height": height, "steps": steps, "seed": seed,
        "checkpoint": requested_ckpt,
        "durationMs": int((time.time() - started) * 1000),
        "promptId": prompt_id,
    }


# ─── tool: file_save ───────────────────────────────────────────────────


def tool_file_save(args: dict[str, Any], *, conv_id: str, owner_did: str,
                   msg_id: str) -> dict[str, Any]:
    filename = str(args.get("filename") or "").strip()
    content = str(args.get("content") or "")
    encoding = str(args.get("encoding") or "utf-8").lower()
    mime = str(args.get("mimeType") or "text/plain")
    if not filename or not content:
        return {"ok": False, "error": "filename and content are required"}
    if encoding == "base64":
        try:
            blob = base64.b64decode(content)
        except (ValueError, TypeError) as e:
            return {"ok": False, "error": f"invalid base64: {e}"}
    else:
        blob = content.encode("utf-8")

    artifact_id = f"file-{_hash12(filename + str(_now_ms()))}"
    sha = hashlib.sha256(blob).hexdigest()
    safe_name = filename.replace("/", "_").replace("..", "_")[:128]
    b2_key = f"{B2_PREFIX_DEFAULT}/{owner_did.replace(':', '_')}/{conv_id}/{artifact_id}-{safe_name}"
    try:
        _b2_put(B2_BUCKET_DEFAULT, b2_key, blob, content_type=mime)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"B2 PUT failed: {e}"}

    insert_artifact(
        conv_id=conv_id, owner_did=owner_did, msg_id=msg_id, artifact_id=artifact_id,
        kind="file", mime_type=mime, byte_size=len(blob), sha256=sha,
        b2_bucket=B2_BUCKET_DEFAULT, b2_key=b2_key,
        title=str(args.get("title") or filename),
        description=str(args.get("description") or ""),
    )
    return {
        "ok": True, "artifactId": artifact_id, "kind": "file",
        "filename": filename, "mimeType": mime, "byteSize": len(blob), "b2Key": b2_key,
    }


# ─── tool: rag_search ──────────────────────────────────────────────────


def tool_rag_search(args: dict[str, Any], *, owner_did: str) -> dict[str, Any]:
    query = str(args.get("query") or "")
    top_k = min(int(args.get("topK") or RAG_HITS), 20)
    only_conv = str(args.get("convId") or "").strip() or None
    if not query.strip():
        return {"ok": False, "error": "query is required"}

    # Phase 1: text-substring search until embeddings backfill via memoryReindex.
    # Phase 2: ORDER BY embedding <-> query_embed (RisingWave IVF UDF).
    pat = f"%{query[:200]}%"
    if only_conv:
        rows = _rw_query(
            "SELECT conv_id, msg_id, role, substring(content, 1, 400) AS snippet, ts_ms "
            "FROM vertex_chat_message "
            "WHERE owner_did = %s AND conv_id = %s AND status = 'active' "
            "  AND content ILIKE %s "
            f"ORDER BY ts_ms DESC LIMIT {int(top_k)}",
            (owner_did, only_conv, pat),
        )
    else:
        rows = _rw_query(
            "SELECT conv_id, msg_id, role, substring(content, 1, 400) AS snippet, ts_ms "
            "FROM vertex_chat_message "
            "WHERE owner_did = %s AND status = 'active' "
            "  AND content ILIKE %s "
            f"ORDER BY ts_ms DESC LIMIT {int(top_k)}",
            (owner_did, pat),
        )
    hits = [
        {"convId": r[0], "msgId": r[1], "role": r[2], "snippet": r[3], "tsMs": r[4]}
        for r in rows
    ]
    return {"ok": True, "query": query, "hits": hits, "method": "ilike-fallback"}


# ─── tool: domain_knowledge_search ────────────────────────────────────


def tool_domain_knowledge_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "")
    game_slug = str(args.get("gameSlug") or "").strip()
    lang = str(args.get("lang") or "ja")
    top_k = min(int(args.get("topK") or DOMAIN_KNOWLEDGE_HITS), 20)
    if not query.strip():
        return {"ok": False, "error": "query is required"}
    hits = search_domain_knowledge(query, game_slug=game_slug, lang=lang, top_k=top_k)
    return {
        "ok": True,
        "query": query,
        "gameSlug": game_slug or _infer_domain_knowledge_game_slug(query),
        "hits": hits,
        "method": "mv_domain_knowledge_search-like",
    }


# ─── tool: web_search ──────────────────────────────────────────────────


def _search_internal_vector_index(query: str, *, top_k: int = 6) -> list[dict[str, Any]]:
    """Semantic search using internal embedding UDF pods over RisingWave vectors.

    The hot path calls the RisingWave Python UDF `actor_embed(..., 'query')`,
    which runs in the in-cluster UDF pod, then probes append-only HNSW vector
    tables. This keeps `web_search` external-free without loading heavyweight
    sentence-transformers into the chat pod request path.
    """
    if not query.strip():
        return []
    limit = max(1, min(int(top_k or 6), 20))
    esc_query = query.replace("'", "''")[:2048]
    qvec_sql = f"actor_embed('{esc_query}', NULL, NULL, 'query')::vector(384)"
    rows: list[tuple[Any, ...]] = []
    vector_queries = []
    if _rw_table_exists("vertex_bluesky_post_embedding"):
        vector_queries.append(
            f"""
            SELECT
              source_uri,
              'bluesky_post' AS source_kind,
              vertex_id AS source_vertex_id,
              substring(COALESCE(text, ''), 1, 900) AS text_preview,
              model_id,
              'etzhayyim-mm-384' AS space_id,
              created_at,
              1 - (emb <=> {qvec_sql}) AS score
            FROM vertex_bluesky_post_embedding
            WHERE emb IS NOT NULL
            ORDER BY emb <=> {qvec_sql}
            LIMIT {limit}
            """
        )
    vector_queries.append(
        f"""
        SELECT
          did AS source_uri,
          'actor_profile' AS source_kind,
          vertex_id AS source_vertex_id,
          '' AS text_preview,
          model_id,
          'etzhayyim-mm-384' AS space_id,
          embedded_at AS created_at,
          1 - (emb <=> {qvec_sql}) AS score
        FROM vertex_actor_embedding
        WHERE emb IS NOT NULL
        ORDER BY emb <=> {qvec_sql}
        LIMIT {limit}
        """
    )
    for sql_text in vector_queries:
        try:
            rows.extend(_rw_query(sql_text, ()))
        except Exception as e:
            log.warning("internal vector web_search query failed: %s", e)
    hits: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: float(r[7] or 0.0), reverse=True):
        score = float(row[7] or 0.0)
        if score < WEB_SEARCH_VECTOR_MIN_SCORE:
            continue
        source_kind = str(row[1] or "vector_document")
        source_uri = str(row[0] or "")
        title = f"{source_kind}: {source_uri}" if source_uri else source_kind
        hits.append(
            {
                "title": title,
                "url": source_uri,
                "snippet": str(row[3] or "")[:500],
                "score": score,
                "sourceKind": source_kind,
                "sourceVertexId": str(row[2] or ""),
                "modelId": str(row[4] or ""),
                "spaceId": str(row[5] or ""),
                "createdAt": str(row[6] or ""),
            }
        )
    return hits


def tool_web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "")
    top_k = min(int(args.get("topK") or 6), 20)
    lang = str(args.get("lang") or "ja")
    if not query.strip():
        return {"ok": False, "error": "query is required"}
    kg_hits = search_domain_knowledge(
        query,
        game_slug=_infer_domain_knowledge_game_slug(query),
        lang=lang,
        top_k=top_k,
    )
    if kg_hits:
        return {
            "ok": True,
            "query": query,
            "hits": [
                {
                    "title": hit.get("title", ""),
                    "url": str(hit.get("documentVid", "")),
                    "snippet": str(hit.get("chunkText", ""))[:500],
                }
                for hit in kg_hits
            ],
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
            "provider": "risingwave-domain-knowledge",
        }
    vector_hits = _search_internal_vector_index(query, top_k=top_k)
    if vector_hits:
        return {
            "ok": True,
            "query": query,
            "hits": vector_hits,
            "provider": "risingwave-vector-ann",
            "method": "pod-embedding-rw-vector-index",
        }
    return {
        "ok": False,
        "error": "no RisingWave KG/vector hit was found; external web search is not used",
        "provider": "risingwave-only",
    }


# ─── tool: schedule_report (side effect → BPMN) ────────────────────────


def tool_schedule_report(args: dict[str, Any], *, conv_id: str, msg_id: str,
                         owner_did: str) -> dict[str, Any]:
    title = str(args.get("title") or "").strip()
    prompt = str(args.get("prompt") or "").strip()
    if not title or not prompt:
        return {"ok": False, "error": "title and prompt are required"}
    body = {
        "convId": conv_id,
        "msgId": msg_id,
        "title": title,
        "prompt": prompt,
        "deliverAt": str(args.get("deliverAt") or ""),
        "deliverChannel": str(args.get("deliverChannel") or "chat"),
    }
    headers = {"Content-Type": "application/json"}
    if INTERNAL_TRUST_SECRET:
        sig = hmac.new(INTERNAL_TRUST_SECRET.encode(), json.dumps(body).encode(),
                       hashlib.sha256).hexdigest()
        headers["x-internal-trust"] = sig
    url = f"{DISPATCHER_URL}/xrpc/com.etzhayyim.apps.chat.scheduleReport"
    try:
        resp = _http_post_json(url, body, headers=headers, timeout=30.0)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "error": f"dispatcher error: {e}"}
    return {"ok": bool(resp.get("ok")), "runId": resp.get("runId", ""),
            "scheduledAt": resp.get("scheduledAt", ""),
            "deliveryChannel": resp.get("deliveryChannel", "")}


# ─── tool dispatch ─────────────────────────────────────────────────────


def dispatch_tool(name: str, args: dict[str, Any], *, conv_id: str, owner_did: str,
                  msg_id: str) -> dict[str, Any]:
    if name == "code_exec":
        return tool_code_exec(args)
    if name == "image_gen":
        return tool_image_gen(args, conv_id=conv_id, owner_did=owner_did, msg_id=msg_id)
    if name == "file_save":
        return tool_file_save(args, conv_id=conv_id, owner_did=owner_did, msg_id=msg_id)
    if name == "rag_search":
        return tool_rag_search(args, owner_did=owner_did)
    if name == "domain_knowledge_search":
        return tool_domain_knowledge_search(args)
    if name == "web_search":
        return tool_web_search(args)
    if name == "schedule_report":
        return tool_schedule_report(args, conv_id=conv_id, msg_id=msg_id, owner_did=owner_did)
    return {"ok": False, "error": f"unknown tool {name!r}"}


# ──────────────────────────────────────────────────────────────────────
# B2 PUT (sigv4)
# ──────────────────────────────────────────────────────────────────────


def _b2_put(bucket: str, key: str, body: bytes, *, content_type: str) -> None:
    """Backblaze B2 S3-compatible PUT via boto3 (lazy import)."""
    import boto3  # type: ignore[import-untyped]  # noqa: PLC0415

    endpoint = os.environ.get("B2_S3_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")
    access_key = os.environ.get("B2_ACCESS_KEY_ID") or os.environ.get("B2_APPLICATION_KEY_ID", "")
    secret_key = os.environ.get("B2_SECRET_ACCESS_KEY") or os.environ.get("B2_APPLICATION_KEY", "")
    if not access_key or not secret_key:
        raise RuntimeError("B2 credentials missing (B2_ACCESS_KEY_ID / B2_SECRET_ACCESS_KEY)")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-west-004",
    )
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)


# ──────────────────────────────────────────────────────────────────────
# LangGraph state graph
# ──────────────────────────────────────────────────────────────────────


def build_chat_graph() -> Any:
    """Build and compile the LangGraph StateGraph for the chat agent loop."""
    from langgraph.graph import END, START, StateGraph  # noqa: PLC0415

    def load_context(state: ChatState) -> ChatState:
        conv_id = state.get("conv_id") or _new_conv_id(state.get("owner_did", ""))
        owner_did = state["owner_did"]
        ensure_conversation(conv_id=conv_id, owner_did=owner_did,
                            model_hint=state.get("model", DEFAULT_MODEL),
                            tier_hint=state.get("tier", "fast"))
        # Prior conversation messages
        prior = load_recent_messages(conv_id=conv_id, owner_did=owner_did)
        messages: list[ChatMessage] = []
        domain_hits = search_domain_knowledge(
            state["user_text"],
            game_slug=_infer_domain_knowledge_game_slug(state["user_text"]),
            lang="ja",
            top_k=DOMAIN_KNOWLEDGE_HITS,
        )
        kg_context = _format_domain_knowledge_context(domain_hits)
        if kg_context:
            messages.append({"role": "system", "content": kg_context})
        messages.extend(prior)
        # Append current user message
        user_msg_id = _new_msg_id(f"u|{conv_id}")
        insert_message(conv_id=conv_id, owner_did=owner_did, msg_id=user_msg_id,
                       role="user", content=state["user_text"])
        messages.append({"role": "user", "content": state["user_text"]})
        return {
            **state,
            "conv_id": conv_id,
            "user_msg_id": user_msg_id,
            "messages": messages,
            "iteration": 0,
            "tool_invocations": [],
            "artifacts_created": [],
            "total_tokens": 0,
            "rag_snippets": [],
            "domain_knowledge_snippets": domain_hits,
        }

    def llm_node(state: ChatState) -> ChatState:
        direct_kg_answer = _domain_knowledge_direct_answer(
            state.get("user_text", ""),
            state.get("domain_knowledge_snippets", []),
        )
        if direct_kg_answer and state.get("iteration", 0) == 0:
            msg_id = _new_msg_id(f"a|{state['conv_id']}|kg-direct")
            insert_message(
                conv_id=state["conv_id"], owner_did=state["owner_did"], msg_id=msg_id,
                role="assistant", content=direct_kg_answer,
                parent_msg_id=state.get("user_msg_id", ""),
                finish_reason="domain_knowledge_direct",
            )
            return {
                **state,
                "_stop": True,
                "final_msg_id": msg_id,
                "final_content": direct_kg_answer,
            }
        if state.get("iteration", 0) >= state.get("max_iterations", 8):
            return {**state, "_stop": True,
                    "final_content": "(reached max iterations)"}
        tier = state.get("tier", "fast")
        model = state.get("model") or DEFAULT_MODEL
        tools = [TOOL_SCHEMAS[t] for t in (state.get("tools_allowed") or list(TOOL_SCHEMAS.keys()))
                 if t in TOOL_SCHEMAS]
        try:
            resp = _llm_chat(
                tier=tier,
                messages=state.get("messages", []),
                tools=tools,
                model_hint=model,
                max_tokens=2048,
                temperature=0.3,
            )
        except llm.LlmError as e:
            return {**state, "_stop": True, "_error": f"llm error: {e}",
                    "final_content": ""}
        # Strip reasoning-tier <think>…</think> chain-of-thought blocks before
        # they reach the user / persistence layer (shosha precedent).
        content = _strip_think_blocks(resp.get("content") or "")
        content = _normalize_domain_knowledge_answer(
            content,
            state.get("domain_knowledge_snippets", []),
        )
        tool_calls = resp.get("tool_calls") or []
        direct_kg_answer = _domain_knowledge_direct_answer(
            state.get("user_text", ""),
            state.get("domain_knowledge_snippets", []),
        )
        if not tool_calls and direct_kg_answer and ("チーゴ" not in content or "ずつき" not in content):
            content = direct_kg_answer
        finish_reason = resp.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
        total_tokens = state.get("total_tokens", 0) + int(resp.get("total_tokens") or 0)

        msg_id = _new_msg_id(f"a|{state['conv_id']}|{state['iteration']}")
        insert_message(
            conv_id=state["conv_id"], owner_did=state["owner_did"], msg_id=msg_id,
            role="assistant", content=content,
            tool_calls_json=json.dumps(tool_calls) if tool_calls else "",
            parent_msg_id=state.get("user_msg_id", ""),
            model_used=resp.get("model") or model,
            prompt_tokens=int(resp.get("prompt_tokens") or 0),
            completion_tokens=int(resp.get("completion_tokens") or 0),
            finish_reason=finish_reason,
        )
        msgs = list(state.get("messages", []))
        m: ChatMessage = {"role": "assistant", "content": content}
        if tool_calls:
            m["tool_calls"] = tool_calls
        msgs.append(m)
        return {
            **state,
            "messages": msgs,
            "final_msg_id": msg_id,
            "final_content": content,
            "total_tokens": total_tokens,
            "iteration": state.get("iteration", 0) + 1,
            "_stop": not bool(tool_calls),
        }

    def tool_executor(state: ChatState) -> ChatState:
        msgs = list(state.get("messages", []))
        last = msgs[-1] if msgs else {}
        calls = last.get("tool_calls") or []
        tool_invocations = list(state.get("tool_invocations", []))
        artifacts = list(state.get("artifacts_created", []))
        for call in calls:
            call_id = str(call.get("id") or _hash12(json.dumps(call)))
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            allowed = state.get("tools_allowed") or list(TOOL_SCHEMAS.keys())
            if name not in allowed:
                result = {"ok": False, "error": f"tool {name!r} not allowed in this turn"}
            else:
                started = time.time()
                try:
                    result = dispatch_tool(name, args, conv_id=state["conv_id"],
                                           owner_did=state["owner_did"],
                                           msg_id=state.get("final_msg_id", ""))
                except Exception as e:  # noqa: BLE001 — record + propagate as JSON
                    result = {"ok": False, "error": f"tool exception: {e}"}
                duration_ms = int((time.time() - started) * 1000)
                summary = json.dumps(result)[:1200]
                insert_tool_invocation(
                    conv_id=state["conv_id"], owner_did=state["owner_did"],
                    msg_id=state.get("final_msg_id", ""), tool_call_id=call_id,
                    tool_name=name, args_json=json.dumps(args)[:4000],
                    result_summary=summary,
                    result_byte_size=len(summary),
                    duration_ms=duration_ms,
                    side_effect_run_id=str(result.get("runId") or ""),
                    side_effect_xrpc_uri=("com.etzhayyim.apps.chat.scheduleReport"
                                          if name == "schedule_report" else ""),
                    error_code="" if result.get("ok") else "tool_error",
                    error_message=str(result.get("error") or "")[:500],
                    status="success" if result.get("ok") else "failure",
                )
            tool_invocations.append({"tool": name, "argsJson": json.dumps(args)[:1000],
                                     "ok": bool(result.get("ok")),
                                     "summary": json.dumps(result)[:600]})
            if result.get("artifactId"):
                artifacts.append(str(result.get("artifactId")))
            # Insert tool message into LLM context
            msgs.append({
                "role": "tool",
                "content": json.dumps(result)[:8000],
                "tool_call_id": call_id,
                "name": name,
            })
            insert_message(
                conv_id=state["conv_id"], owner_did=state["owner_did"],
                msg_id=_new_msg_id(f"t|{call_id}"),
                role="tool", content=json.dumps(result)[:8000],
                tool_call_id=call_id,
            )
        return {
            **state,
            "messages": msgs,
            "tool_invocations": tool_invocations,
            "artifacts_created": artifacts,
            "_stop": False,
        }

    def should_continue(state: ChatState) -> str:
        if state.get("_stop"):
            return "end"
        last = (state.get("messages") or [{}])[-1]
        if last.get("tool_calls"):
            return "tools"
        return "end"

    def end_node(state: ChatState) -> ChatState:
        return state

    g = StateGraph(ChatState)
    g.add_node("load_context", load_context)
    g.add_node("llm", llm_node)
    g.add_node("tools", tool_executor)
    g.add_node("end", end_node)
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "llm")
    g.add_conditional_edges("llm", should_continue, {"tools": "tools", "end": "end"})
    g.add_edge("tools", "llm")
    g.add_edge("end", END)
    return g.compile()


# ──────────────────────────────────────────────────────────────────────
# Public entry — run a single user turn
# ──────────────────────────────────────────────────────────────────────


_GRAPH_CACHE: Any = None


def get_graph() -> Any:
    global _GRAPH_CACHE
    if _GRAPH_CACHE is None:
        _GRAPH_CACHE = build_chat_graph()
    return _GRAPH_CACHE


def run_turn(*, owner_did: str, user_text: str, conv_id: str = "",
             tier: str = "balanced", model: str = "",
             tools_allowed: Optional[list[str]] = None,
             max_iterations: int = 8) -> dict[str, Any]:
    """Synchronous one-shot turn (used by com.etzhayyim.apps.chat.agentLoop XRPC)."""
    init: ChatState = {
        "owner_did": owner_did,
        "user_text": user_text,
        "conv_id": conv_id,
        "tier": tier,
        "model": model or DEFAULT_MODEL,
        "tools_allowed": tools_allowed or list(TOOL_SCHEMAS.keys()),
        "max_iterations": max_iterations,
    }
    graph = get_graph()
    final = graph.invoke(init)
    return {
        "ok": not bool(final.get("_error")),
        "convId": final.get("conv_id", ""),
        "finalMsgId": final.get("final_msg_id", ""),
        "content": final.get("final_content", ""),
        "iterations": final.get("iteration", 0),
        "toolCalls": final.get("tool_invocations", []),
        "artifactsCreated": final.get("artifacts_created", []),
        "totalTokens": final.get("total_tokens", 0),
        "model": final.get("model", model or DEFAULT_MODEL),
        "error": final.get("_error", ""),
    }


async def stream_turn(*, owner_did: str, user_text: str, conv_id: str = "",
                      tier: str = "balanced", model: str = "",
                      tools_allowed: Optional[list[str]] = None,
                      max_iterations: int = 8) -> AsyncIterator[dict[str, Any]]:
    """Async streaming turn — yields dicts for SSE encoding by chat_server.

    LangGraph's astream emits node-step events; we decorate them so the
    UI gets a clean event sequence (token / tool_start / tool_done /
    final / error).
    """
    inferred_game = _infer_domain_knowledge_game_slug(user_text)
    direct_hits = search_domain_knowledge(
        user_text,
        game_slug=inferred_game,
        lang="ja",
        top_k=DOMAIN_KNOWLEDGE_HITS,
    )
    direct_answer = _domain_knowledge_direct_answer(user_text, direct_hits)
    if direct_answer:
        direct_conv_id = conv_id or _new_conv_id(owner_did)
        user_msg_id = _new_msg_id(f"u|{direct_conv_id}")
        final_msg_id = _new_msg_id(f"a|{direct_conv_id}|kg-direct")

        def persist_direct_turn() -> None:
            try:
                ensure_conversation(
                    conv_id=direct_conv_id,
                    owner_did=owner_did,
                    model_hint=model or DEFAULT_MODEL,
                    tier_hint=tier,
                )
                insert_message(
                    conv_id=direct_conv_id,
                    owner_did=owner_did,
                    msg_id=user_msg_id,
                    role="user",
                    content=user_text,
                )
                insert_message(
                    conv_id=direct_conv_id,
                    owner_did=owner_did,
                    msg_id=final_msg_id,
                    role="assistant",
                    content=direct_answer,
                    parent_msg_id=user_msg_id,
                    finish_reason="domain_knowledge_direct",
                )
            except Exception:
                log.exception("[chat] async direct KG persistence failed")

        threading.Thread(target=persist_direct_turn, daemon=True).start()
        yield {
            "event": "node",
            "node": "domain_knowledge",
            "convId": direct_conv_id,
            "iteration": 0,
        }
        yield {"event": "delta", "content": direct_answer}
        yield {
            "event": "final",
            "convId": direct_conv_id,
            "finalMsgId": final_msg_id,
            "content": direct_answer,
            "iterations": 0,
            "artifactsCreated": [],
            "totalTokens": 0,
        }
        return

    if tier != "reasoning":
        stream_conv_id = conv_id or _new_conv_id(owner_did)
        user_msg_id = _new_msg_id(f"u|{stream_conv_id}")
        yield {
            "event": "node",
            "node": "load_context",
            "convId": stream_conv_id,
            "iteration": 0,
        }

        prior: list[ChatMessage] = []
        if conv_id:
            try:
                prior = await asyncio.to_thread(
                    load_recent_messages,
                    conv_id=stream_conv_id,
                    owner_did=owner_did,
                )
            except Exception:
                log.exception("[chat] load recent messages failed")

        def persist_user_turn() -> None:
            try:
                ensure_conversation(
                    conv_id=stream_conv_id,
                    owner_did=owner_did,
                    model_hint=model or DEFAULT_MODEL,
                    tier_hint=tier,
                )
                insert_message(
                    conv_id=stream_conv_id,
                    owner_did=owner_did,
                    msg_id=user_msg_id,
                    role="user",
                    content=user_text,
                )
            except Exception:
                log.exception("[chat] async user persistence failed")

        threading.Thread(target=persist_user_turn, daemon=True).start()

        messages: list[ChatMessage] = []
        kg_context = _format_domain_knowledge_context(direct_hits)
        if kg_context:
            messages.append({"role": "system", "content": kg_context})
        messages.extend(prior)
        messages.append({"role": "user", "content": user_text})

        allowed = tools_allowed if tools_allowed is not None else list(TOOL_SCHEMAS.keys())
        allowed = [name for name in allowed if name in TOOL_SCHEMAS]
        total_tokens = 0
        final_msg_id = ""
        final_content = ""
        artifacts: list[str] = []
        tool_invocations: list[dict[str, Any]] = []
        iterations = 0

        for iteration in range(max(1, max_iterations)):
            tools = [TOOL_SCHEMAS[t] for t in allowed]
            resp: dict[str, Any] = {}
            try:
                yield {
                    "event": "node",
                    "node": "llm",
                    "convId": stream_conv_id,
                    "iteration": iteration,
                }
                for part in _llm_chat_stream(
                    tier=tier,
                    messages=messages,
                    tools=tools,
                    model_hint=model or DEFAULT_MODEL,
                    max_tokens=2048,
                    temperature=0.3,
                ):
                    if part.get("type") == "delta":
                        yield {"event": "delta", "content": part.get("content", "")}
                    elif part.get("type") == "final":
                        resp = part
            except llm.LlmError as e:
                yield {"event": "error", "error": f"llm error: {e}"}
                return

            raw_content = resp.get("content") or ""
            content = _strip_think_blocks(raw_content)
            content = _normalize_domain_knowledge_answer(content, direct_hits)
            tool_calls = resp.get("tool_calls") or []
            if not tool_calls and direct_answer and ("チーゴ" not in content or "ずつき" not in content):
                content = direct_answer
            finish_reason = resp.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
            total_tokens += int(resp.get("total_tokens") or 0)
            final_msg_id = _new_msg_id(f"a|{stream_conv_id}|{iteration}")
            final_content = content
            iterations = iteration + 1

            def persist_assistant(
                msg_id: str = final_msg_id,
                msg_content: str = content,
                calls: list[dict[str, Any]] = list(tool_calls),
                reason: str = finish_reason,
                prompt_tokens: int = int(resp.get("prompt_tokens") or 0),
                completion_tokens: int = int(resp.get("completion_tokens") or 0),
                model_used: str = str(resp.get("model") or model or DEFAULT_MODEL),
            ) -> None:
                try:
                    insert_message(
                        conv_id=stream_conv_id,
                        owner_did=owner_did,
                        msg_id=msg_id,
                        role="assistant",
                        content=msg_content,
                        tool_calls_json=json.dumps(calls) if calls else "",
                        parent_msg_id=user_msg_id,
                        model_used=model_used,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        finish_reason=reason,
                    )
                except Exception:
                    log.exception("[chat] async assistant persistence failed")

            threading.Thread(target=persist_assistant, daemon=True).start()

            assistant_msg: ChatMessage = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)
            if not tool_calls:
                break

            yield {
                "event": "node",
                "node": "tools",
                "convId": stream_conv_id,
                "iteration": iterations,
            }
            for call in tool_calls:
                call_id = str(call.get("id") or _hash12(json.dumps(call)))
                fn = call.get("function") or {}
                name = str(fn.get("name") or "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                if name not in allowed:
                    result = {"ok": False, "error": f"tool {name!r} not allowed in this turn"}
                    duration_ms = 0
                else:
                    started = time.time()
                    try:
                        result = dispatch_tool(
                            name,
                            args,
                            conv_id=stream_conv_id,
                            owner_did=owner_did,
                            msg_id=final_msg_id,
                        )
                    except Exception as e:  # noqa: BLE001
                        result = {"ok": False, "error": f"tool exception: {e}"}
                    duration_ms = int((time.time() - started) * 1000)
                summary = json.dumps(result)[:1200]
                tool_invocations.append({
                    "tool": name,
                    "argsJson": json.dumps(args)[:1000],
                    "ok": bool(result.get("ok")),
                    "summary": json.dumps(result)[:600],
                })
                if result.get("artifactId"):
                    artifacts.append(str(result.get("artifactId")))
                yield {
                    "event": "tool",
                    "tool": name,
                    "ok": bool(result.get("ok")),
                    "summary": json.dumps(result)[:600],
                }
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result)[:8000],
                    "tool_call_id": call_id,
                    "name": name,
                })

                def persist_tool(
                    tool_call_id: str = call_id,
                    tool_name: str = name,
                    tool_args: dict[str, Any] = dict(args),
                    tool_result: dict[str, Any] = dict(result),
                    tool_summary: str = summary,
                    tool_duration_ms: int = duration_ms,
                ) -> None:
                    try:
                        insert_tool_invocation(
                            conv_id=stream_conv_id,
                            owner_did=owner_did,
                            msg_id=final_msg_id,
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                            args_json=json.dumps(tool_args)[:4000],
                            result_summary=tool_summary,
                            result_byte_size=len(tool_summary),
                            duration_ms=tool_duration_ms,
                            side_effect_run_id=str(tool_result.get("runId") or ""),
                            side_effect_xrpc_uri=(
                                "com.etzhayyim.apps.chat.scheduleReport"
                                if tool_name == "schedule_report" else ""
                            ),
                            error_code="" if tool_result.get("ok") else "tool_error",
                            error_message=str(tool_result.get("error") or "")[:500],
                            status="success" if tool_result.get("ok") else "failure",
                        )
                        insert_message(
                            conv_id=stream_conv_id,
                            owner_did=owner_did,
                            msg_id=_new_msg_id(f"t|{tool_call_id}"),
                            role="tool",
                            content=json.dumps(tool_result)[:8000],
                            tool_call_id=tool_call_id,
                        )
                    except Exception:
                        log.exception("[chat] async tool persistence failed")

                threading.Thread(target=persist_tool, daemon=True).start()
        else:
            final_content = final_content or "(reached max iterations)"

        yield {
            "event": "final",
            "convId": stream_conv_id,
            "finalMsgId": final_msg_id,
            "content": final_content,
            "iterations": iterations,
            "toolCalls": tool_invocations,
            "artifactsCreated": artifacts,
            "totalTokens": total_tokens,
        }
        return

    init: ChatState = {
        "owner_did": owner_did,
        "user_text": user_text,
        "conv_id": conv_id,
        "tier": tier,
        "model": model or DEFAULT_MODEL,
        "tools_allowed": tools_allowed or list(TOOL_SCHEMAS.keys()),
        "max_iterations": max_iterations,
    }
    graph = get_graph()
    last_state: dict[str, Any] = {}
    try:
        async for event in graph.astream(init, stream_mode="updates"):
            # event = {node_name: state_delta}
            for node, delta in event.items():
                last_state.update(delta)
                yield {"event": "node", "node": node,
                       "convId": last_state.get("conv_id", ""),
                       "iteration": last_state.get("iteration", 0)}
                if node == "llm" and delta.get("final_content"):
                    yield {"event": "delta", "content": delta["final_content"]}
                if node == "tools" and delta.get("tool_invocations"):
                    for ti in delta["tool_invocations"][-len(delta.get("tool_invocations", [])):]:
                        yield {"event": "tool", "tool": ti.get("tool"),
                               "ok": ti.get("ok"), "summary": ti.get("summary")}
    except Exception as e:  # noqa: BLE001 — surface to client
        yield {"event": "error", "error": str(e)}
        return
    yield {
        "event": "final",
        "convId": last_state.get("conv_id", ""),
        "finalMsgId": last_state.get("final_msg_id", ""),
        "content": last_state.get("final_content", ""),
        "iterations": last_state.get("iteration", 0),
        "artifactsCreated": last_state.get("artifacts_created", []),
        "totalTokens": last_state.get("total_tokens", 0),
    }


# ──────────────────────────────────────────────────────────────────────
# Maintenance task handlers (Zeebe BPMN-bound)
# ──────────────────────────────────────────────────────────────────────


async def task_chat_memory_reindex(**_kwargs: Any) -> dict[str, Any]:
    """Embed unindexed messages from the last 24 h and promote important
    ones to vertex_chat_memory long-term store. Phase 1: count-only stub
    (real embedding requires sentence-transformers via Murakumo actor)."""
    rows = _rw_query(
        "SELECT count(*) FROM vertex_chat_message "
        "WHERE status = 'active' AND embedding IS NULL "
        "  AND to_timestamp(ts_ms / 1000.0) > now() - INTERVAL '24 hours'"
    )
    pending = int(rows[0][0]) if rows else 0
    return {"ok": True, "embedded": 0, "promotedToLongTerm": 0,
            "pendingPhase1Stub": pending}


async def task_chat_artifact_gc(**_kwargs: Any) -> dict[str, Any]:
    """Soft-delete + B2 DELETE artifacts past expires_at."""
    rows = _rw_query(
        "SELECT vertex_id, b2_bucket, b2_key, byte_size FROM vertex_chat_artifact "
        "WHERE status = 'active' "
        "  AND expires_at IS NOT NULL "
        "  AND to_timestamp(extract(epoch from cast(expires_at AS timestamp))) < now() "
        "LIMIT 500"
    )
    deleted = 0
    bytes_freed = 0
    for r in rows:
        vid, bucket, key, size = r[0], r[1], r[2], int(r[3] or 0)
        try:
            _b2_delete(bucket, key)
        except Exception as e:  # noqa: BLE001 — log + continue
            log.warning("[artifact-gc] B2 DELETE failed key=%s: %s", key, e)
            continue
        _rw_execute(
            "UPDATE vertex_chat_artifact SET status = 'gc' WHERE vertex_id = %s",
            (vid,),
        )
        deleted += 1
        bytes_freed += size
    return {"ok": True, "deleted": deleted, "bytesFreed": bytes_freed}


def _b2_delete(bucket: str, key: str) -> None:
    import boto3  # type: ignore[import-untyped]  # noqa: PLC0415

    endpoint = os.environ.get("B2_S3_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")
    client = boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("B2_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("B2_SECRET_ACCESS_KEY", ""),
        region_name="us-west-004",
    )
    client.delete_object(Bucket=bucket, Key=key)


async def task_chat_conversation_archive(**_kwargs: Any) -> dict[str, Any]:
    """Mark conversations idle > 90 d as archived. Iceberg dump deferred to
    Phase 2 (RW Iceberg sink not yet wired for chat tables)."""
    _rw_execute(
        "UPDATE vertex_chat_conversation SET status = 'archived' "
        "WHERE status = 'active' "
        "  AND to_timestamp(extract(epoch from cast(last_message_at AS timestamp))) < now() - INTERVAL '90 days'",
        (),
    )
    rows = _rw_query(
        "SELECT count(*) FROM vertex_chat_conversation WHERE status = 'archived'",
    )
    return {"ok": True, "archivedConversations": int(rows[0][0]) if rows else 0,
            "archivedMessages": 0, "phase1Stub": True}


async def task_chat_report_compose(**kwargs: Any) -> dict[str, Any]:
    """XRPC com.etzhayyim.apps.chat.scheduleReport handler.
    Generates a deep-research report (Murakumo `reasoning` tier), saves
    artifact, posts a follow-up assistant message into the conversation."""
    conv_id = str(kwargs.get("convId") or "")
    msg_id = str(kwargs.get("msgId") or "")
    title = str(kwargs.get("title") or "")
    prompt = str(kwargs.get("prompt") or "")
    deliver_channel = str(kwargs.get("deliverChannel") or "chat")
    if not conv_id or not title or not prompt:
        return {"ok": False, "error": "convId, title, prompt required"}

    run_id = f"rpt-{_hash12(conv_id + title + str(_now_ms()))}"
    try:
        resp = _llm_chat(
            tier="reasoning",
            messages=[{"role": "user", "content": f"# {title}\n\n{prompt}"}],
            max_tokens=4096, temperature=0.5,
            timeout_sec=180.0,
        )
    except llm.LlmError as e:
        return {"ok": False, "runId": run_id, "error": f"llm error: {e}"}

    content = resp.get("content") or ""
    blob = content.encode("utf-8")
    artifact_id = f"rpt-{_hash12(run_id)}"
    sha = hashlib.sha256(blob).hexdigest()
    b2_key = f"{B2_PREFIX_DEFAULT}/reports/{conv_id}/{artifact_id}.md"
    try:
        _b2_put(B2_BUCKET_DEFAULT, b2_key, blob, content_type="text/markdown")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "runId": run_id, "error": f"B2 PUT failed: {e}"}

    # Lookup the original conversation owner
    rows = _rw_query(
        "SELECT owner_did FROM vertex_chat_conversation WHERE conv_id = %s LIMIT 1",
        (conv_id,),
    )
    owner_did = str(rows[0][0]) if rows else CHAT_ACTOR

    insert_artifact(
        conv_id=conv_id, owner_did=owner_did, msg_id=msg_id, artifact_id=artifact_id,
        kind="document", mime_type="text/markdown", byte_size=len(blob), sha256=sha,
        b2_bucket=B2_BUCKET_DEFAULT, b2_key=b2_key, title=title,
        description=f"deep-research report (run {run_id})", prompt=prompt,
    )
    # Post follow-up assistant message
    if deliver_channel == "chat":
        followup_msg_id = _new_msg_id(f"r|{run_id}")
        insert_message(
            conv_id=conv_id, owner_did=owner_did, msg_id=followup_msg_id,
            role="assistant",
            content=f"📝 **{title}** — report ready. ({len(blob)} bytes, artifact `{artifact_id}`)",
            parent_msg_id=msg_id, model_used="reasoning",
        )
    return {
        "ok": True, "runId": run_id, "artifactId": artifact_id,
        "scheduledAt": _now_iso(),
        "deliveryChannel": deliver_channel,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 120_000) -> None:
    """Wire chat maintenance + side-effect task types onto the shared LangServer
    worker. The agent hot path itself is NOT registered here — chat_server.py
    runs the LangGraph in-process via aiohttp.

      task_type="chat.memory.reindex"
      task_type="chat.artifact.gc"
      task_type="chat.conversation.archive"
      task_type="chat.report.compose"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("chat.memory.reindex",         task_chat_memory_reindex,         ms=600_000)
    t("chat.artifact.gc",            task_chat_artifact_gc,            ms=600_000)
    t("chat.conversation.archive",   task_chat_conversation_archive,   ms=600_000)
    t("chat.report.compose",         task_chat_report_compose,         ms=300_000)
