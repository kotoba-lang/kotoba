"""server.py — FastAPI entry for the ameno Path-B daemon.

Mirrors the TS daemon's Hono server (ADR-2605191229):

    GET  /healthz                       → {status, workerDid}
    GET  /workerInfo                    → {did, uptimeMs, model, ollamaReachable, ...}
    POST /threads/:tid/invoke           → run graph, return final state
    POST /threads/:tid/stream           → SSE stream of GraphChunk
    GET  /threads/:tid/state            → latest checkpointed state

Authoritative ADR: 90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from kotodama.local_llm import LocalLlmConfig

from .did_auth import issue_nonce, verify_did_sig
from .file_checkpointer import FileCheckpointer
from .ollama_stream import check_ollama_ready
from .pregel import _maybe_mst_checkpointer, build_graph, invoke_ameno


AMENO_HOME = Path(os.environ.get("AMENO_HOME", str(Path.home() / ".ameno")))
CHECKPOINTER_PATH = AMENO_HOME / "checkpointer.json"
DID_PATH = AMENO_HOME / "worker-did"
HOST = os.environ.get("AMENO_HOST", "127.0.0.1")
PORT = int(os.environ.get("AMENO_PORT", "12481"))  # 12481 (TS daemon uses 12480)
# Bearer-token gate. Empty/unset = unauthenticated mode (localhost only).
# ADR-2605191407 §sec.
AUTH_TOKEN = os.environ.get("AMENO_AUTH_TOKEN", "").strip()
STARTED_AT = time.time()


def _safe_hostname() -> str:
    h = socket.gethostname()
    out = "".join(c for c in h if c.isalnum() or c == "-")[:32]
    return out or "anon"


def _get_or_create_did() -> str:
    try:
        if DID_PATH.exists():
            stored = DID_PATH.read_text("utf-8").strip()
            if stored.startswith("did:web:host:"):
                return stored
    except OSError:
        pass
    new = f"did:web:host:{_safe_hostname()}-{uuid.uuid4().hex}"
    try:
        DID_PATH.parent.mkdir(parents=True, exist_ok=True)
        DID_PATH.write_text(new, "utf-8")
    except OSError:
        pass
    return new


AMENO_HOME.mkdir(parents=True, exist_ok=True)
WORKER_DID = _get_or_create_did()
# Stage 2 (substrate persistence) takes precedence when the sidecar
# env vars are present. Stage 1 (file-backed local persistence) is the
# fallback for dev / standalone Path B daemons. ADR-2605191257.
MST_SAVER = _maybe_mst_checkpointer()
if MST_SAVER is not None:
    CHECKPOINTER: Any = MST_SAVER
    CHECKPOINTER_KIND = "mst"
else:
    CHECKPOINTER = FileCheckpointer(CHECKPOINTER_PATH)
    CHECKPOINTER_KIND = "file"
GRAPH = build_graph(CHECKPOINTER)

# Heartbeat counters
_recent_briefs: list[float] = []
_total_briefs = 0
_total_tokens = 0
_last_error: str | None = None
_BRIEF_WINDOW_SEC = 60.0


def _note_brief(tokens: int) -> None:
    global _total_briefs, _total_tokens
    now = time.time()
    _recent_briefs.append(now)
    _total_briefs += 1
    _total_tokens += tokens
    cutoff = now - _BRIEF_WINDOW_SEC
    while _recent_briefs and _recent_briefs[0] < cutoff:
        _recent_briefs.pop(0)


def _note_error(msg: str) -> None:
    global _last_error
    _last_error = msg


app = FastAPI(title="ameno-daemon", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["authorization", "content-type"],
)


@app.middleware("http")
async def _auth_gate(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Accept either Bearer (ADR-2605191407) or DIDSig (ADR-2605191657).
    /healthz and /auth/nonce are exempt."""
    path = request.url.path
    if path == "/healthz" or path == "/auth/nonce":
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if header.startswith("DIDSig "):
        r = verify_did_sig(header)
        if not r.ok:
            return JSONResponse({"error": r.error or "unauthorized"}, status_code=401)
        return await call_next(request)
    if not AUTH_TOKEN:
        # Loopback dev — no bearer configured and no DIDSig present.
        return await call_next(request)
    if header != f"Bearer {AUTH_TOKEN}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/auth/nonce")
async def auth_nonce() -> dict[str, Any]:
    """Single-use 60s-TTL nonce for DIDSig auth. ADR-2605191657."""
    return issue_nonce()


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok", "workerDid": WORKER_DID}


@app.get("/workerInfo")
async def worker_info() -> dict[str, Any]:
    cfg = LocalLlmConfig.from_env()
    ollama = await check_ollama_ready(cfg.model)
    return {
        "did": WORKER_DID,
        "uptimeMs": int((time.time() - STARTED_AT) * 1000),
        "briefsPerMinute": len(_recent_briefs),
        "totalBriefs": _total_briefs,
        "totalTokensDecoded": _total_tokens,
        "lastError": _last_error,
        "model": cfg.model,
        "ollamaBase": cfg.endpoint,
        "ollamaReachable": ollama.get("reachable", False),
        "ollamaModelInstalled": ollama.get("modelInstalled", False),
        "home": str(AMENO_HOME),
        "kind": "path-b-python",
        "checkpointer": CHECKPOINTER_KIND,
    }


def _normalise_messages(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("system", "user", "assistant"):
            role = "user"
        content = m.get("content") if isinstance(m.get("content"), str) else ""
        out.append({"role": role, "content": content})
    return out


@app.post("/threads/{tid}/invoke")
async def invoke(tid: str, request: Request) -> JSONResponse:
    body = await request.json()
    messages = _normalise_messages(body.get("messages"))
    max_iter = int(body.get("maxIterations", 0))
    active = bool(body.get("activeInference", False))
    tools_on = bool(body.get("toolsEnabled", True))
    tokens = {"n": 0}

    def collect(chunk: dict[str, Any]) -> None:
        if chunk.get("type") == "stats" and chunk.get("phase") == "generate":
            stats = chunk.get("stats") or {}
            tokens["n"] = int(stats.get("totalTokens", 0))

    try:
        draft = await invoke_ameno(
            messages=messages,
            max_iterations=max_iter,
            active_inference=active,
            tools_enabled=tools_on,
            thread_id=tid,
            on_chunk=collect,
            graph=GRAPH,
        )
        _note_brief(tokens["n"])
        return JSONResponse({"thread_id": tid, "draft": draft})
    except Exception as e:
        _note_error(str(e))
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/threads/{tid}/stream")
async def stream(tid: str, request: Request) -> StreamingResponse:
    body = await request.json()
    messages = _normalise_messages(body.get("messages"))
    max_iter = int(body.get("maxIterations", 0))
    active = bool(body.get("activeInference", False))
    tools_on = bool(body.get("toolsEnabled", True))

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    tokens = {"n": 0}

    def emit(chunk: dict[str, Any]) -> None:
        if chunk.get("type") == "stats" and chunk.get("phase") == "generate":
            stats = chunk.get("stats") or {}
            tokens["n"] = int(stats.get("totalTokens", 0))
        queue.put_nowait(chunk)

    async def runner() -> None:
        try:
            draft = await invoke_ameno(
                messages=messages,
                max_iterations=max_iter,
                active_inference=active,
                tools_enabled=tools_on,
                thread_id=tid,
                on_chunk=emit,
                graph=GRAPH,
            )
            _note_brief(tokens["n"])
            queue.put_nowait({"type": "done", "draft": draft})
        except Exception as e:
            _note_error(str(e))
            queue.put_nowait({"type": "error", "error": str(e)})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(runner())

    async def gen() -> AsyncIterator[bytes]:
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n".encode("utf-8")
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
    )


@app.get("/threads/{tid}/state")
async def thread_state(tid: str) -> dict[str, Any]:
    """Return parsed graph state for a thread. ADR-2605191645 — browser
    viewer mode pulls this to seed its local message list when the user
    switches into daemon mode."""
    cfg = {"configurable": {"thread_id": tid}}
    snapshot = await GRAPH.aget_state(cfg)
    if snapshot is None:
        return {"thread_id": tid, "values": None}
    # snapshot.values is a TypedDict view; copy to a plain dict so
    # FastAPI's JSON encoder can serialise it.
    return {"thread_id": tid, "values": dict(snapshot.values or {})}


def main() -> None:
    import uvicorn

    banner = (
        f"ameno-daemon (Path B / Python) listening on http://{HOST}:{PORT}\n"
        f"  did:        {WORKER_DID}\n"
        f"  home:       {AMENO_HOME}\n"
        f"  model:      {LocalLlmConfig.from_env().model}\n"
        f"  endpoint:   {LocalLlmConfig.from_env().endpoint}\n"
    )
    print(banner)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
