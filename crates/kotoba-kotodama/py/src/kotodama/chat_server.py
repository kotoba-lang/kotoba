"""etzhayyim.com chat — aiohttp HTTP server entrypoint.

Hot path for the chat product. CF Worker (etzhayyim.com) → CF Tunnel
(chat-agent.etzhayyim.com) → ClusterIP `chat-agent.mitama-chat-pool.svc:8080`
→ this server.

Routes:
    POST /api/chat                          SSE streaming agent loop (browser)
    POST /xrpc/com.etzhayyim.apps.chat.sendMessage non-streaming single-shot
    POST /xrpc/com.etzhayyim.apps.chat.agentLoop  non-streaming agent loop
    GET  /xrpc/com.etzhayyim.apps.chat.coverage   counts
    GET  /xrpc/com.etzhayyim.apps.chat.listConversations
    GET  /xrpc/com.etzhayyim.apps.chat.getConversation
    POST /xrpc/com.etzhayyim.apps.chat.deleteConversation
    GET  /health
    GET  /_app/meta

Run:
    python -m kotodama.chat_server

Env:
    CHAT_LISTEN_HOST   default 0.0.0.0
    CHAT_LISTEN_PORT   default 8080
    DATABASE_URL       RisingWave PG :4566 (used by db_sync)
    VULTR_SERVERLESS_KEY  Murakumo / LiteLLM API key (kotodama.llm)
    B2_*               artifact storage credentials
    BPMN_DISPATCHER_INTERNAL_URL  for schedule_report side-effect tool

Auth model (Phase 1):
    The `viewer-did` HTTP header is treated as the caller's DID. The CF
    Worker (chat-shell) is responsible for validating the AT Protocol
    session cookie (atproto.etzhayyim.com) and attaching this header before
    forwarding here. Anonymous browser sessions get
    `viewer-did = did:web:etzhayyim.com:anon:<sha-of-ip-ua>`.

    The internal-trust HMAC (CHAT_INTERNAL_SECRET) verifies that the
    request originated from the CF Tunnel (not the public Internet).
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from kotodama.primitives import chat as chat_mod

LOG = logging.getLogger("chat_server")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

LISTEN_HOST = os.environ.get("CHAT_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("CHAT_LISTEN_PORT", "8080"))
INTERNAL_TRUST_SECRET = os.environ.get("CHAT_INTERNAL_SECRET", "")
ANON_DID_PREFIX = "did:web:etzhayyim.com:anon:"


# ──────────────────────────────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────────────────────────────


def _viewer_did(request: web.Request) -> str:
    """Resolve the caller's DID from headers. Falls back to anon DID
    derived from IP+UA hash."""
    explicit = request.headers.get("viewer-did") or request.headers.get("x-viewer-did")
    if explicit and explicit.startswith("did:"):
        return explicit
    ip = request.headers.get("cf-connecting-ip") or (
        request.remote or "0.0.0.0")
    ua = request.headers.get("user-agent") or ""
    fp = hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:24]
    return f"{ANON_DID_PREFIX}{fp}"


def _tools_allowed_from_payload(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("tools")
    if isinstance(raw, list):
        if not raw:
            return []
        names: list[str] = []
        for item in raw:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                fn = item.get("function") or {}
                names.append(str(fn.get("name") or item.get("name") or ""))
        return [name for name in names if name in chat_mod.TOOL_SCHEMAS]
    return [name for name in chat_mod.TOOL_SCHEMAS.keys() if name != "web_search"]


def _verify_internal_trust(request: web.Request, body: bytes) -> bool:
    """If CHAT_INTERNAL_SECRET is set, require x-internal-trust HMAC.
    If unset, accept all (open in single-tenant pod)."""
    if not INTERNAL_TRUST_SECRET:
        return True
    sig = request.headers.get("x-internal-trust") or ""
    expected = hmac.new(INTERNAL_TRUST_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


# ──────────────────────────────────────────────────────────────────────
# Hot path — POST /api/chat (SSE)
# ──────────────────────────────────────────────────────────────────────


async def post_chat_sse(request: web.Request) -> web.StreamResponse:
    body = await request.read()
    if not _verify_internal_trust(request, body):
        return web.json_response({"error": "Forbidden"}, status=403)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return web.json_response({"error": "InvalidJSON"}, status=400)

    text = str(payload.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "text is required"}, status=400)

    owner_did = _viewer_did(request)
    conv_id = str(payload.get("convId") or "")
    tier = str(payload.get("tier") or "balanced")
    model = str(payload.get("modelHint") or "")
    tools = _tools_allowed_from_payload(payload) if "tools" in payload else []
    max_iter = min(int(payload.get("maxIterations") or 8), 16)

    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)
    try:
        start_ev = {
            "event": "start",
            "convId": conv_id,
            "stage": "accepted",
            "message": "accepted",
        }
        await resp.write(
            f"data: {json.dumps(start_ev, ensure_ascii=False)}\n\n".encode("utf-8"),
        )
        await resp.drain()
        async for ev in chat_mod.stream_turn(
            owner_did=owner_did, user_text=text, conv_id=conv_id,
            tier=tier, model=model, tools_allowed=list(tools),
            max_iterations=max_iter,
        ):
            line = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            await resp.write(line.encode("utf-8"))
            await resp.drain()
    except asyncio.CancelledError:
        LOG.info("[chat-sse] client disconnect mid-stream")
        raise
    except Exception as e:  # noqa: BLE001 — emit error event then close
        LOG.exception("[chat-sse] stream error")
        err = json.dumps({"event": "error", "error": str(e)})
        await resp.write(f"data: {err}\n\n".encode())
    await resp.write(b"data: {\"event\":\"done\"}\n\n")
    await resp.write_eof()
    return resp


# ──────────────────────────────────────────────────────────────────────
# XRPC — non-streaming
# ──────────────────────────────────────────────────────────────────────


async def xrpc_send_message(request: web.Request) -> web.Response:
    body = await request.read()
    if not _verify_internal_trust(request, body):
        return web.json_response({"error": "Forbidden"}, status=403)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "error": "InvalidJSON"}, status=400)
    text = str(payload.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "error": "text is required"}, status=400)

    owner_did = _viewer_did(request)
    # sendMessage = single-shot, no tool calls (tools_allowed=[])
    out = await asyncio.to_thread(
        chat_mod.run_turn,
        owner_did=owner_did, user_text=text,
        conv_id=str(payload.get("convId") or ""),
        tier=str(payload.get("tier") or "fast"),
        model=str(payload.get("modelHint") or ""),
        tools_allowed=[], max_iterations=1,
    )
    return web.json_response({
        "ok": out.get("ok", False),
        "convId": out.get("convId", ""),
        "msgId": out.get("finalMsgId", ""),
        "role": "assistant",
        "content": out.get("content", ""),
        "model": out.get("model", ""),
        "completionTokens": out.get("totalTokens", 0),
        "error": out.get("error", ""),
    })


async def xrpc_agent_loop(request: web.Request) -> web.Response:
    body = await request.read()
    if not _verify_internal_trust(request, body):
        return web.json_response({"error": "Forbidden"}, status=403)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "error": "InvalidJSON"}, status=400)
    text = str(payload.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "error": "text is required"}, status=400)

    owner_did = _viewer_did(request)
    tools = _tools_allowed_from_payload(payload)
    out = await asyncio.to_thread(
        chat_mod.run_turn,
        owner_did=owner_did, user_text=text,
        conv_id=str(payload.get("convId") or ""),
        tier=str(payload.get("tier") or "balanced"),
        model=str(payload.get("modelHint") or ""),
        tools_allowed=list(tools),
        max_iterations=min(int(payload.get("maxIterations") or 8), 16),
    )
    return web.json_response(out)


async def xrpc_coverage(request: web.Request) -> web.Response:
    def _q(sql: str) -> int:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql)
            row = (_res[0] if _res else None)
            return int(row[0]) if row else 0
    return web.json_response({
        "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "conversations": _q(
            "SELECT count(*) FROM vertex_chat_conversation WHERE status='active'"),
        "messages": _q(
            "SELECT count(*) FROM vertex_chat_message WHERE status='active'"),
        "artifacts": _q(
            "SELECT count(*) FROM vertex_chat_artifact WHERE status='active'"),
        "active24h": _q(
            "SELECT count(*) FROM mv_chat_active_24h"),
        "totalArtifactBytes": _q(
            "SELECT COALESCE(SUM(total_bytes), 0) FROM mv_chat_artifact_size_per_owner"),
    })


async def xrpc_list_conversations(request: web.Request) -> web.Response:
    owner_did = _viewer_did(request)
    limit = min(int(request.query.get("limit", "50")), 200)
    status = request.query.get("status", "active")
    sql = (
        "SELECT conv_id, title, message_count, last_message_at, status, agent_did, model_hint "
        "FROM vertex_chat_conversation WHERE owner_did = %s "
    )
    if status != "all":
        sql += "AND status = %s "
        sql += f"ORDER BY last_message_at DESC LIMIT {int(limit)}"
        if True:
            client = get_kotoba_client()
            _res = client.q(sql, (owner_did, status))
            rows = list(_res)
    else:
        sql += f"ORDER BY last_message_at DESC LIMIT {int(limit)}"
        if True:
            client = get_kotoba_client()
            _res = client.q(sql, (owner_did,))
            rows = list(_res)
    return web.json_response({
        "conversations": [
            {
                "convId": r[0], "title": r[1] or "(untitled)",
                "messageCount": int(r[2] or 0), "lastMessageAt": r[3] or "",
                "status": r[4] or "active", "agentDid": r[5] or "",
                "modelHint": r[6] or "",
            }
            for r in rows
        ],
    })


async def xrpc_get_conversation(request: web.Request) -> web.Response:
    owner_did = _viewer_did(request)
    conv_id = request.query.get("convId", "").strip()
    if not conv_id:
        return web.json_response({"error": "convId required"}, status=400)
    limit = min(int(request.query.get("limit", "200")), 1000)
    include_artifacts = request.query.get("includeArtifacts", "true").lower() == "true"
    include_invocations = request.query.get(
        "includeToolInvocations", "true").lower() == "true"

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT title, agent_did, model_hint, message_count, last_message_at "
            "FROM vertex_chat_conversation WHERE conv_id = %s AND owner_did = %s LIMIT 1",
            (conv_id, owner_did),
        )
        head = (_res[0] if _res else None)
        if not head:
            return web.json_response({"error": "NotFound", "convId": conv_id}, status=404)

        _res = client.q(
            "SELECT msg_id, role, content, ts_ms, model_used, total_tokens, "
            "       tool_calls_json, tool_call_id "
            "FROM vertex_chat_message "
            "WHERE conv_id = %s AND status = 'active' "
            f"ORDER BY ts_ms ASC LIMIT {int(limit)}",
            (conv_id,),
        )
        msg_rows = list(_res)

        artifacts: list[dict[str, Any]] = []
        if include_artifacts:
            _res = client.q(
                "SELECT artifact_id, kind, mime_type, byte_size, title, b2_key "
                "FROM vertex_chat_artifact "
                "WHERE conv_id = %s AND status = 'active' "
                "ORDER BY ts_ms ASC LIMIT 200",
                (conv_id,),
            )
            for r in _res:
                artifacts.append({
                    "artifactId": r[0], "kind": r[1], "mimeType": r[2],
                    "byteSize": int(r[3] or 0), "title": r[4] or "",
                    "url": f"https://etzhayyim.com/api/chat/artifact/{r[0]}",
                })

        invocations: list[dict[str, Any]] = []
        if include_invocations:
            _res = client.q(
                "SELECT tool_name, msg_id, args_json, result_summary, duration_ms, status "
                "FROM vertex_chat_tool_invocation "
                "WHERE conv_id = %s "
                "ORDER BY ts_ms ASC LIMIT 200",
                (conv_id,),
            )
            for r in _res:
                invocations.append({
                    "toolName": r[0], "msgId": r[1], "argsJson": r[2] or "",
                    "resultSummary": r[3] or "", "durationMs": int(r[4] or 0),
                    "status": r[5] or "success",
                })

    return web.json_response({
        "convId": conv_id,
        "title": head[0] or "", "agentDid": head[1] or "",
        "modelHint": head[2] or "", "messageCount": int(head[3] or 0),
        "lastMessageAt": head[4] or "",
        "messages": [
            {
                "msgId": r[0], "role": r[1] or "user", "content": r[2] or "",
                "tsMs": int(r[3] or 0), "modelUsed": r[4] or "",
                "totalTokens": int(r[5] or 0),
                "toolCallsJson": r[6] or "", "toolCallId": r[7] or "",
            }
            for r in msg_rows
        ],
        "artifacts": artifacts,
        "toolInvocations": invocations,
    })


async def xrpc_delete_conversation(request: web.Request) -> web.Response:
    body = await request.read()
    if not _verify_internal_trust(request, body):
        return web.json_response({"error": "Forbidden"}, status=403)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "error": "InvalidJSON"}, status=400)
    conv_id = str(payload.get("convId") or "").strip()
    purge_now = bool(payload.get("purgeNow"))
    if not conv_id:
        return web.json_response({"ok": False, "error": "convId required"}, status=400)
    owner_did = _viewer_did(request)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "UPDATE vertex_chat_conversation SET status = 'deleted' "
            "WHERE conv_id = %s AND owner_did = %s",
            (conv_id, owner_did),
        )
        _res = client.q(
            "UPDATE vertex_chat_message SET status = 'deleted' "
            "WHERE conv_id = %s AND owner_did = %s",
            (conv_id, owner_did),
        )
        scheduled = 0
        if purge_now:
            new_expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 60))
            _res = client.q(
                "UPDATE vertex_chat_artifact SET expires_at = %s "
                "WHERE conv_id = %s AND owner_did = %s AND status = 'active'",
                (new_expires, conv_id, owner_did),
            )
            _res = client.q(
                "SELECT count(*) FROM vertex_chat_artifact "
                "WHERE conv_id = %s AND owner_did = %s AND status = 'active'",
                (conv_id, owner_did),
            )
            row = (_res[0] if _res else None)
            scheduled = int(row[0]) if row else 0

    return web.json_response({
        "ok": True, "messagesAffected": -1,
        "artifactsScheduledForGc": scheduled,
    })


# ──────────────────────────────────────────────────────────────────────
# OpenAI-compatible API (/v1/*)
# ──────────────────────────────────────────────────────────────────────
#
# Surface (Phase 1):
#   GET  /v1/models                  list catalogued chat models
#   POST /v1/chat/completions        OpenAI Chat Completions API
#                                    (streaming + non-streaming, tool calling)
#
# Authentication: Phase 1 accepts any `Authorization: Bearer …` header (or
# none). The header is recorded in the `x-etzhayyim-viewer-did` derivation but
# not validated. Phase 2 will check `sk_live_*` keys against the AT
# Protocol vault and the AuthN Worker.
#
# Model name → tier mapping:
#   etzhayyim-chat / etzhayyim-chat-balanced    → tier=balanced (Vultr Devstral-2-123B)
#   etzhayyim-chat-fast                    → tier=fast
#   etzhayyim-chat-reasoning               → tier=reasoning (Qwen3.5-397B)
#   any other                         → treated as model_hint, tier=balanced
#
# Tools: OpenAI clients can pass `tools=[…]` — these are merged into the
# agent's tool whitelist for the turn. If absent, all built-in tools are
# available. To run "plain LLM with no tool access", pass `tools=[]`.

_OPENAI_MODELS: list[dict[str, Any]] = [
    {"id": "etzhayyim-chat", "object": "model", "owned_by": "etzhayyim",
     "description": "etzhayyim chat assistant (default). Built-in tools: code, image, file save, history search, web search."},
    {"id": "etzhayyim-chat-fast", "object": "model", "owned_by": "etzhayyim",
     "description": "Lower-latency variant for short replies."},
    {"id": "etzhayyim-chat-balanced", "object": "model", "owned_by": "etzhayyim",
     "description": "Balanced quality + speed (alias for etzhayyim-chat)."},
    {"id": "etzhayyim-chat-reasoning", "object": "model", "owned_by": "etzhayyim",
     "description": "Higher-quality reasoning for harder tasks (slower)."},
]

_MODEL_TO_TIER: dict[str, str] = {
    "etzhayyim-chat":           "balanced",
    "etzhayyim-chat-balanced":  "balanced",
    "etzhayyim-chat-fast":      "fast",
    "etzhayyim-chat-reasoning": "reasoning",
}


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user":
            content = m.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # OpenAI multimodal: pull text parts only (image_url ignored Phase 1).
                parts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                if parts:
                    return "\n".join(parts)
    return ""


def _openai_chat_id() -> str:
    return f"chatcmpl-{int(time.time() * 1000):x}"


async def openai_list_models(_request: web.Request) -> web.Response:
    return web.json_response({
        "object": "list",
        "data": [{**m, "created": int(time.time())} for m in _OPENAI_MODELS],
    })


async def openai_chat_completions(request: web.Request) -> web.StreamResponse:
    body = await request.read()
    if not _verify_internal_trust(request, body):
        return web.json_response(
            {"error": {"message": "Forbidden", "type": "auth_error", "code": "403"}},
            status=403,
        )
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON", "type": "invalid_request_error"}},
            status=400,
        )

    messages = payload.get("messages") or []
    user_text = _last_user_text(messages)
    if not user_text:
        return web.json_response(
            {"error": {"message": "No user message in `messages`",
                       "type": "invalid_request_error"}},
            status=400,
        )

    model = str(payload.get("model") or "etzhayyim-chat")
    tier = _MODEL_TO_TIER.get(model, "balanced")
    # If the caller asked for a non-etzhayyim model name (e.g. "gpt-4o-mini"), pass
    # it through as a model_hint so the upstream LLM sees the requested name.
    model_hint = "" if model.startswith("etzhayyim-chat") else model

    stream = bool(payload.get("stream"))
    max_tokens = min(int(payload.get("max_tokens") or 2048), 8192)
    # Custom OpenAI-compat extensions (top-level or nested in extra_body).
    extra = payload.get("extra_body") or {}
    conv_id = str(payload.get("conv_id") or extra.get("conv_id") or "")
    max_iterations = min(int(
        payload.get("max_iterations") or extra.get("max_iterations") or 8,
    ), 16)

    # Tool whitelist: OpenAI standard `tools` field, falls back to all built-ins.
    raw_tools = payload.get("tools")
    if isinstance(raw_tools, list):
        if len(raw_tools) == 0:
            tools_allowed: list[str] = []   # explicit "no tools"
        else:
            # Extract tool names; reject unknown ones with a warning later.
            tools_allowed = [
                str((t.get("function") or {}).get("name") or "")
                for t in raw_tools
                if isinstance(t, dict)
            ]
            tools_allowed = [n for n in tools_allowed if n in chat_mod.TOOL_SCHEMAS]
    else:
        tools_allowed = list(chat_mod.TOOL_SCHEMAS.keys())

    owner_did = _viewer_did(request)
    chat_id = _openai_chat_id()
    created = int(time.time())

    # ── Streaming path (OpenAI SSE chunks) ────────────────────────────
    if stream:
        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )
        await resp.prepare(request)

        async def write_chunk(payload: dict[str, Any]) -> None:
            line = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await resp.write(line.encode("utf-8"))
            await resp.drain()

        # Initial role chunk per OpenAI convention.
        await write_chunk({
            "id": chat_id, "object": "chat.completion.chunk",
            "created": created, "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"},
                         "finish_reason": None}],
        })

        etzhayyim_meta: dict[str, Any] = {}
        try:
            async for ev in chat_mod.stream_turn(
                owner_did=owner_did, user_text=user_text,
                conv_id=conv_id, tier=tier, model=model_hint,
                tools_allowed=tools_allowed, max_iterations=max_iterations,
            ):
                if ev["event"] == "delta":
                    await write_chunk({
                        "id": chat_id, "object": "chat.completion.chunk",
                        "created": created, "model": model,
                        "choices": [{"index": 0,
                                     "delta": {"content": ev.get("content", "")},
                                     "finish_reason": None}],
                    })
                elif ev["event"] == "tool":
                    # Surface tool activity in a etzhayyim-specific chunk extension
                    # (OpenAI clients ignore unknown fields). Cleaner than
                    # spamming `delta.content`.
                    await write_chunk({
                        "id": chat_id, "object": "chat.completion.chunk",
                        "created": created, "model": model,
                        "choices": [{"index": 0, "delta": {},
                                     "finish_reason": None}],
                        "x_etzhayyim": {"tool": ev.get("tool"),
                                   "ok": ev.get("ok"),
                                   "summary": ev.get("summary")},
                    })
                elif ev["event"] == "final":
                    etzhayyim_meta = {
                        "convId": ev.get("convId"),
                        "finalMsgId": ev.get("finalMsgId"),
                        "iterations": ev.get("iterations"),
                        "artifactsCreated": ev.get("artifactsCreated", []),
                        "totalTokens": ev.get("totalTokens", 0),
                    }
                elif ev["event"] == "error":
                    await write_chunk({
                        "id": chat_id, "object": "chat.completion.chunk",
                        "created": created, "model": model,
                        "choices": [{"index": 0, "delta": {},
                                     "finish_reason": "error"}],
                        "x_etzhayyim": {"error": ev.get("error")},
                    })
        except asyncio.CancelledError:
            LOG.info("[openai-sse] client disconnect")
            raise
        except Exception as e:  # noqa: BLE001
            LOG.exception("[openai-sse] stream error")
            await write_chunk({
                "id": chat_id, "object": "chat.completion.chunk",
                "created": created, "model": model,
                "choices": [{"index": 0, "delta": {},
                             "finish_reason": "error"}],
                "x_etzhayyim": {"error": str(e)},
            })

        # Final chunk with finish_reason.
        await write_chunk({
            "id": chat_id, "object": "chat.completion.chunk",
            "created": created, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "x_etzhayyim": etzhayyim_meta,
        })
        # OpenAI sentinel terminator.
        await resp.write(b"data: [DONE]\n\n")
        await resp.write_eof()
        return resp

    # ── Non-streaming path ────────────────────────────────────────────
    out = await asyncio.to_thread(
        chat_mod.run_turn,
        owner_did=owner_did, user_text=user_text,
        conv_id=conv_id, tier=tier, model=model_hint,
        tools_allowed=tools_allowed, max_iterations=max_iterations,
    )
    if not out.get("ok"):
        return web.json_response(
            {"error": {"message": out.get("error") or "agent error",
                       "type": "agent_error"}},
            status=502,
        )
    total_tokens = int(out.get("totalTokens") or 0)
    # Best-effort prompt/completion split.  Phase 1 doesn't separate the two;
    # we put 0 for prompt and total for completion.  Standard OpenAI clients
    # tolerate this.
    return web.json_response({
        "id": chat_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": out.get("content", "")},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": total_tokens,
                  "total_tokens": total_tokens},
        "x_etzhayyim": {
            "convId": out.get("convId"),
            "finalMsgId": out.get("finalMsgId"),
            "iterations": out.get("iterations"),
            "artifactsCreated": out.get("artifactsCreated", []),
            "toolCalls": out.get("toolCalls", []),
        },
    })


# ──────────────────────────────────────────────────────────────────────
# MCP — Model Context Protocol server (Streamable HTTP / JSON-RPC 2.0)
# ──────────────────────────────────────────────────────────────────────
#
# Surface (Phase 1):
#   POST /mcp        Streamable HTTP transport (request-response)
#   GET  /mcp        Stream open-ended SSE for server-initiated messages (Phase 2)
#
# Implements the MCP spec methods needed by Claude Desktop / Cursor /
# Aider / Continue:
#   initialize / initialized notification
#   tools/list   tools/call
#   prompts/list (empty Phase 1)
#   resources/list (empty Phase 1)
#
# Tools exposed (matches LangGraph internal tools but callable directly):
#   code_exec   image_gen   file_save   rag_search   web_search
#   schedule_report
#   chat        wraps the agent loop — same surface as POST /v1/chat/completions
#
# `did:web:etzhayyim.com` already advertises this endpoint at
# https://etzhayyim.com/mcp via the chat-shell Worker's /.well-known/did.json.

MCP_PROTOCOL_VERSION = "2025-03-26"
MCP_SERVER_NAME = "etzhayyim-chat-mcp"
MCP_SERVER_VERSION = "0.1.0"


def _mcp_tool_definitions() -> list[dict[str, Any]]:
    """Project chat-agent's TOOL_SCHEMAS (OpenAI function format) into MCP tool
    descriptors (`name` + `description` + `inputSchema`)."""
    out: list[dict[str, Any]] = []
    for name, schema in chat_mod.TOOL_SCHEMAS.items():
        fn = schema.get("function") or {}
        out.append({
            "name": name,
            "description": fn.get("description") or "",
            "inputSchema": fn.get("parameters") or {"type": "object"},
        })
    # Plus the meta-tool that wraps the full agent loop.
    out.append({
        "name": "chat",
        "description": (
            "Run a single user turn through the etzhayyim chat agent (LangGraph + "
            "LLM + internal tools). Returns the assistant's reply text."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string", "maxLength": 32000},
                "convId": {"type": "string"},
                "tier": {"type": "string", "enum": ["fast", "balanced", "reasoning"]},
                "modelHint": {"type": "string"},
                "tools_allowed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sub-tool whitelist. Pass [] for plain LLM.",
                },
                "maxIterations": {"type": "integer", "default": 8, "maximum": 16},
            },
        },
    })
    return out


def _mcp_error(req_id: Any, code: int, message: str,
               data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _mcp_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _mcp_dispatch_call(name: str, args: dict[str, Any], *,
                       owner_did: str) -> dict[str, Any]:
    """Run an MCP tools/call invocation. Returns an MCP `content` array
    (list of `{type: "text", text: ...}` blocks) which is the standard
    MCP tool result shape."""
    if name == "chat":
        text = str(args.get("text") or "")
        if not text:
            return {"isError": True, "content": [{
                "type": "text", "text": "text is required",
            }]}
        out = chat_mod.run_turn(
            owner_did=owner_did, user_text=text,
            conv_id=str(args.get("convId") or ""),
            tier=str(args.get("tier") or "balanced"),
            model=str(args.get("modelHint") or ""),
            tools_allowed=list(args.get("tools_allowed") or
                               chat_mod.TOOL_SCHEMAS.keys()),
            max_iterations=min(int(args.get("maxIterations") or 8), 16),
        )
        return {
            "isError": not out.get("ok", False),
            "content": [{"type": "text", "text": out.get("content", "")}],
            "structuredContent": {
                "convId": out.get("convId"),
                "finalMsgId": out.get("finalMsgId"),
                "iterations": out.get("iterations"),
                "artifactsCreated": out.get("artifactsCreated", []),
                "totalTokens": out.get("totalTokens", 0),
                "model": out.get("model", ""),
            },
        }

    if name not in chat_mod.TOOL_SCHEMAS:
        return {"isError": True, "content": [{
            "type": "text", "text": f"Unknown tool: {name!r}",
        }]}

    # Tools that need conv/msg context — synthesize a "mcp-direct" conversation
    # so the resulting artifact rows are still referentially valid.
    conv_id = f"mcp-{int(time.time())}"
    msg_id = f"mcp-{int(time.time() * 1000)}"
    chat_mod.ensure_conversation(
        conv_id=conv_id, owner_did=owner_did, title="(MCP direct call)",
    )
    chat_mod.insert_message(
        conv_id=conv_id, owner_did=owner_did, msg_id=msg_id,
        role="user", content=f"mcp:tools/call {name}",
    )

    result = chat_mod.dispatch_tool(name, args, conv_id=conv_id,
                                    owner_did=owner_did, msg_id=msg_id)
    return {
        "isError": not result.get("ok", False),
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
        "structuredContent": result,
    }


def _mcp_handle_request(req: dict[str, Any], *, owner_did: str) -> dict[str, Any] | None:
    """Process a single MCP JSON-RPC request. Returns the response dict, or
    None for notifications (which don't produce a response)."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    # Notifications: no response.
    if req_id is None:
        return None

    if method == "initialize":
        return _mcp_result(req_id, {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "prompts": {"listChanged": False},
                "resources": {"listChanged": False},
                "logging": {},
            },
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": MCP_SERVER_VERSION,
            },
            "instructions": (
                "etzhayyim chat MCP server. Use `chat` for full agent invocation, "
                "or call individual tools (code_exec / image_gen / file_save / "
                "rag_search / web_search / schedule_report) directly."
            ),
        })

    if method == "tools/list":
        return _mcp_result(req_id, {"tools": _mcp_tool_definitions()})

    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _mcp_error(req_id, -32602,
                              "Invalid params: arguments must be an object")
        try:
            result = _mcp_dispatch_call(name, args, owner_did=owner_did)
        except Exception as e:  # noqa: BLE001
            LOG.exception("[mcp] tools/call %s failed", name)
            return _mcp_error(req_id, -32603, f"internal error: {e}")
        return _mcp_result(req_id, result)

    if method == "prompts/list":
        return _mcp_result(req_id, {"prompts": []})

    if method == "resources/list":
        return _mcp_result(req_id, {"resources": []})

    if method == "ping":
        return _mcp_result(req_id, {})

    return _mcp_error(req_id, -32601, f"Method not found: {method}")


async def mcp_post(request: web.Request) -> web.StreamResponse:
    """MCP Streamable HTTP — POST endpoint.
    Per spec: server MAY respond with `application/json` (single response) or
    `text/event-stream` (one or more SSE events ending with the response).
    Phase 1: we always reply application/json for simplicity. Streaming is
    available via /v1/chat/completions which already speaks SSE."""
    body = await request.read()
    if not _verify_internal_trust(request, body):
        return web.json_response(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32001, "message": "Forbidden"}},
            status=403,
        )
    try:
        msg = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return web.json_response(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32700, "message": "Parse error"}},
            status=400,
        )

    owner_did = _viewer_did(request)

    # Batched requests (rare; supported for spec compliance).
    if isinstance(msg, list):
        responses: list[dict[str, Any]] = []
        for m in msg:
            r = _mcp_handle_request(m, owner_did=owner_did)
            if r is not None:
                responses.append(r)
        return web.json_response(responses)

    if not isinstance(msg, dict):
        return web.json_response(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32600, "message": "Invalid Request"}},
            status=400,
        )

    resp = _mcp_handle_request(msg, owner_did=owner_did)
    if resp is None:
        # Notification — return 202 Accepted with no body per MCP spec.
        return web.Response(status=202)
    return web.json_response(resp)


async def mcp_get(_request: web.Request) -> web.Response:
    """MCP server info probe (humans hitting the URL in a browser) +
    optional SSE channel for server-initiated messages.

    Phase 1: returns a small JSON describing the server — no SSE channel yet.
    """
    return web.json_response({
        "name": MCP_SERVER_NAME,
        "version": MCP_SERVER_VERSION,
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "transport": "streamable-http",
        "did": chat_mod.CHAT_ACTOR,
        "tools": [t["name"] for t in _mcp_tool_definitions()],
        "documentation": "POST JSON-RPC 2.0 messages to this URL. See https://modelcontextprotocol.io/",
    })


# ──────────────────────────────────────────────────────────────────────
# Health / meta
# ──────────────────────────────────────────────────────────────────────


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "app": "chat-agent",
                              "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})


async def app_meta(_request: web.Request) -> web.Response:
    return web.json_response({
        "app": "etzhayyim-chat-agent",
        "did": chat_mod.CHAT_ACTOR,
        "tools": list(chat_mod.TOOL_SCHEMAS.keys()),
        "defaultModel": "etzhayyim-chat",
        "version": "0.1.0",
    })


# ──────────────────────────────────────────────────────────────────────
# App factory
# ──────────────────────────────────────────────────────────────────────


def make_app() -> web.Application:
    app = web.Application(client_max_size=64 * 1024 * 1024)  # 64 MB upload cap
    async def _warm_domain_knowledge(_app: web.Application) -> None:
        async def _run() -> None:
            try:
                await asyncio.to_thread(chat_mod.warm_domain_knowledge_lookup_cache, "pokemon-pokopia")
                LOG.info("[chat-server] warmed pokemon-pokopia domain knowledge lookup cache")
            except Exception as e:  # noqa: BLE001
                LOG.warning("[chat-server] domain knowledge cache warm failed: %s", e)

        asyncio.create_task(_run())

    app.on_startup.append(_warm_domain_knowledge)
    app.add_routes([
        web.post("/api/chat", post_chat_sse),
        web.post("/xrpc/com.etzhayyim.apps.chat.sendMessage", xrpc_send_message),
        web.post("/xrpc/com.etzhayyim.apps.chat.agentLoop", xrpc_agent_loop),
        web.get("/xrpc/com.etzhayyim.apps.chat.coverage", xrpc_coverage),
        web.get("/xrpc/com.etzhayyim.apps.chat.listConversations", xrpc_list_conversations),
        web.get("/xrpc/com.etzhayyim.apps.chat.getConversation", xrpc_get_conversation),
        web.post("/xrpc/com.etzhayyim.apps.chat.deleteConversation", xrpc_delete_conversation),
        # OpenAI-compatible API surface.
        web.get("/v1/models", openai_list_models),
        web.post("/v1/chat/completions", openai_chat_completions),
        # MCP (Model Context Protocol) — Streamable HTTP transport.
        web.post("/mcp", mcp_post),
        web.get("/mcp", mcp_get),
        web.get("/health", health),
        web.get("/_app/meta", app_meta),
        # LangGraph Server protocol — required by @langchain/svelte useStream.
        web.post("/threads", lg_post_threads),
        web.get("/threads/{thread_id}", lg_get_thread),
        web.post("/threads/{thread_id}/commands", lg_post_thread_commands),
        web.post("/threads/{thread_id}/stream/events", lg_post_thread_stream_events),
        web.get("/assistants/search", lg_get_assistants_search),
    ])
    return app


# ──────────────────────────────────────────────────────────────────────
# LangGraph Server protocol (v2 SSE) — Thread / Stream API
#
# Implements the minimal wire protocol required by:
#   @langchain/langgraph-sdk ProtocolSseTransportAdapter
#   @langchain/svelte useStream
#
# Endpoints:
#   POST /threads                          create thread
#   GET  /threads/{id}                     get thread
#   POST /threads/{id}/commands            dispatch command (run.start, …)
#   POST /threads/{id}/stream/events       SSE event stream (subscribe)
#   GET  /assistants/search                list assistants
#
# Protocol wire format — each SSE event body is a JSON object:
#   {"type":"event","method":<channel>,"params":{"namespace":[],"data":<payload>},
#    "event_id":<uuid>,"seq":<int>}
# ──────────────────────────────────────────────────────────────────────

_LG_THREADS: dict[str, dict[str, Any]] = {}
_LG_EVENT_SUBS: dict[str, list[asyncio.Queue]] = {}
_LG_CLOSED = object()  # sentinel that closes a subscriber queue

_LG_ASSISTANT = {
    "assistant_id": "agent",
    "graph_id": "chat",
    "name": "etzhayyim.com Chat Agent",
    "description": "etzhayyim.com LangGraph chat agent",
    "config": {},
    "context": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "metadata": {},
    "version": 1,
}


def _lg_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _lg_ensure_thread(tid: str) -> None:
    if tid not in _LG_THREADS:
        _LG_THREADS[tid] = {
            "thread_id": tid, "created_at": _lg_now(), "updated_at": _lg_now(),
            "metadata": {}, "config": {}, "context": None,
            "status": "idle", "values": None, "interrupts": [],
        }
        _LG_EVENT_SUBS[tid] = []


async def _lg_broadcast(tid: str, method: str, data: Any, seq: list[int]) -> None:
    seq[0] += 1
    event = {
        "type": "event",
        "method": method,
        "params": {"namespace": [], "data": data},
        "event_id": str(uuid.uuid4()),
        "seq": seq[0],
    }
    for q in list(_LG_EVENT_SUBS.get(tid, [])):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def lg_post_threads(request: web.Request) -> web.Response:
    body_bytes = await request.read()
    body = json.loads(body_bytes) if body_bytes else {}
    tid = body.get("thread_id") or str(uuid.uuid4())
    _lg_ensure_thread(tid)
    return web.json_response(_LG_THREADS[tid])


async def lg_get_thread(request: web.Request) -> web.Response:
    tid = request.match_info["thread_id"]
    _lg_ensure_thread(tid)
    return web.json_response(_LG_THREADS[tid])


async def lg_post_thread_commands(request: web.Request) -> web.Response:
    tid = request.match_info["thread_id"]
    _lg_ensure_thread(tid)
    body_bytes = await request.read()
    body = json.loads(body_bytes) if body_bytes else {}
    cmd = body.get("type") or ""

    if cmd == "run.start":
        viewer_did = _viewer_did(request)
        inp = body.get("input") or {}
        config = body.get("config") or {}
        metadata = body.get("metadata") or {}

        lc_messages: list[dict] = inp.get("messages") or []
        user_text = ""
        for msg in lc_messages:
            if isinstance(msg, dict) and msg.get("type") in ("human", "user"):
                c = msg.get("content", "")
                user_text = c if isinstance(c, str) else (
                    " ".join(
                        x.get("text", "") if isinstance(x, dict) else str(x)
                        for x in c
                    ) if isinstance(c, list) else ""
                )

        if not user_text:
            return web.json_response({"error": "No human message in input"}, status=400)

        configurable = config.get("configurable") or {}
        conv_id = metadata.get("conv_id") or _LG_THREADS[tid].get("_conv_id", "")
        tier = configurable.get("tier", "balanced")
        model = configurable.get("model_hint", "")

        _LG_THREADS[tid]["status"] = "busy"
        asyncio.create_task(_lg_run(tid, viewer_did, user_text, conv_id, tier, model))
        return web.Response(status=202)

    return web.Response(status=202)


async def _lg_run(
    tid: str, viewer_did: str, user_text: str,
    conv_id: str, tier: str, model: str,
) -> None:
    seq: list[int] = [0]
    run_id = str(uuid.uuid4())
    ai_msg_id = f"ai-{run_id[:8]}"
    human_msg_id = f"hu-{run_id[:8]}"
    ai_content = ""

    try:
        async for ev in chat_mod.stream_turn(
            owner_did=viewer_did, user_text=user_text,
            conv_id=conv_id, tier=tier, model=model,
        ):
            event_type = ev.get("event")
            if event_type == "start":
                cid = ev.get("convId") or ""
                if cid:
                    _LG_THREADS[tid]["_conv_id"] = cid
            elif event_type == "delta":
                ai_content += ev.get("content", "")
                await _lg_broadcast(tid, "messages", [
                    {"type": "ai", "content": ai_content, "id": ai_msg_id}
                ], seq)
            elif event_type == "final":
                final = ev.get("content") or ai_content
                cid = ev.get("convId") or _LG_THREADS[tid].get("_conv_id", "")
                if cid:
                    _LG_THREADS[tid]["_conv_id"] = cid
                state: dict = {"messages": [
                    {"type": "human", "content": user_text, "id": human_msg_id},
                    {"type": "ai", "content": final, "id": ai_msg_id},
                ]}
                _LG_THREADS[tid]["values"] = state
                await _lg_broadcast(tid, "values", state, seq)

        _LG_THREADS[tid]["status"] = "idle"
        await _lg_broadcast(tid, "lifecycle", {"event": "completed"}, seq)
    except Exception as e:
        LOG.exception("[lg-run] thread=%s", tid)
        _LG_THREADS[tid]["status"] = "error"
        await _lg_broadcast(tid, "lifecycle", {"event": "failed", "error": str(e)}, seq)

    for q in list(_LG_EVENT_SUBS.get(tid, [])):
        try:
            q.put_nowait(_LG_CLOSED)
        except asyncio.QueueFull:
            pass


async def lg_post_thread_stream_events(request: web.Request) -> web.StreamResponse:
    tid = request.match_info["thread_id"]
    _lg_ensure_thread(tid)

    q: asyncio.Queue = asyncio.Queue(maxsize=512)
    _LG_EVENT_SUBS.setdefault(tid, []).append(q)

    resp = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)

    try:
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=25.0)
            except asyncio.TimeoutError:
                await resp.write(b": keepalive\n\n")
                continue
            if item is _LG_CLOSED:
                break
            data = json.dumps(item, ensure_ascii=False)
            await resp.write(f"data: {data}\n\n".encode())
    except (asyncio.CancelledError, ConnectionResetError):
        LOG.debug("[lg-stream] client disconnect tid=%s", tid)
    except Exception:
        LOG.exception("[lg-stream] error tid=%s", tid)
    finally:
        subs = _LG_EVENT_SUBS.get(tid)
        if subs:
            try:
                subs.remove(q)
            except ValueError:
                pass

    return resp


async def lg_get_assistants_search(request: web.Request) -> web.Response:
    return web.json_response([_LG_ASSISTANT])


def main() -> None:
    app = make_app()
    LOG.info("[chat-server] listening on %s:%d (default model=%s)",
             LISTEN_HOST, LISTEN_PORT, chat_mod.DEFAULT_MODEL)
    web.run_app(app, host=LISTEN_HOST, port=LISTEN_PORT, access_log=None)


if __name__ == "__main__":
    main()
