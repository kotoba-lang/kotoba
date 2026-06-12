"""langserver_client — Pregel-cell-side helpers for querying fleet LSPs (L9 root).

Companion to ``50-infra/etzhayyim-langserver/`` substrate. A Pregel cell that
needs symbol-aware information (hover / definition / references / rename) about
code residing on a Mac mini opens an LSP JSON-RPC session to the fleet
langserver and drives it directly from the cell's async loop.

Transport:
  - Reads ``50-infra/etzhayyim-langserver/scripts/lsp-fleet.json`` (the L5
    fleet registry) to resolve mesh-IP + TCP port per language.
  - Speaks LSP framing (Content-Length headers + JSON-RPC body) over a raw
    asyncio stream. No third-party deps — stdlib only, mirrors the
    healthz-sidecar style.

Scope (L9 minimum):
  - ``LangserverClient`` — async context manager, one connection per session
  - ``initialize`` / ``shutdown`` lifecycle
  - ``hover`` / ``definition`` / ``references`` / ``rename`` convenience helpers
  - Selectable transport: ``tcp`` (default, mesh-wide) or ``unix`` (same-host)

Out of scope (post-L9):
  - workspace/didChange replication (cells don't typically edit through LSP)
  - LSP multiplexer (one LSP shared across many concurrent cells) —
    socat fork is sufficient until otherwise demonstrated

Constraints (per CLAUDE.md):
  - This file lives in 20-actors/kotoba-kotodama/py (Apache 2.0 + Charter Rider via
    repo-root /CHARTER-RIDER.md). No legacy ``etzhayyim-`` prefix.
  - Substrate hard rules apply: LSP traffic is COMPUTATION ONLY (no MST /
    IPFS / L2 writes from this module). State writes happen in the calling
    cell, not here.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


# ── Substrate-fit invariant (mirrors joucho_murakumo.py pattern) ─────────

if "runpod" in os.environ.get("PATH", "").lower() or os.environ.get("RW_URL"):
    raise ImportError(
        "langserver_client religious-corp-only — RUNPOD/RW environment detected."
    )


# ── Registry resolution ──────────────────────────────────────────────────

_DEFAULT_REGISTRY_REL = "50-infra/etzhayyim-langserver/scripts/lsp-fleet.json"


def _find_registry(explicit: str | None = None) -> pathlib.Path:
    """Locate lsp-fleet.json. Search order:

    1. ``explicit`` argument
    2. ``$ETZHAYYIM_LANGSERVER_REGISTRY`` env var
    3. ``$ETZHAYYIM_REPO`` + default relative path
    4. walk up from this file looking for ``etzhayyim/root``
    """
    candidates: list[pathlib.Path] = []
    if explicit:
        candidates.append(pathlib.Path(explicit))
    env_path = os.environ.get("ETZHAYYIM_LANGSERVER_REGISTRY")
    if env_path:
        candidates.append(pathlib.Path(env_path))
    repo_env = os.environ.get("ETZHAYYIM_REPO")
    if repo_env:
        candidates.append(pathlib.Path(repo_env) / _DEFAULT_REGISTRY_REL)
    # Walk up from this file
    here = pathlib.Path(__file__).resolve()
    for ancestor in [here, *here.parents]:
        candidate = ancestor / _DEFAULT_REGISTRY_REL
        if candidate.exists():
            candidates.append(candidate)
            break
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "lsp-fleet.json not found. Run "
        "50-infra/etzhayyim-langserver/scripts/generate-fleet-registry.sh "
        "or set $ETZHAYYIM_LANGSERVER_REGISTRY."
    )


@dataclass(slots=True, frozen=True)
class LangserverEndpoint:
    lang: str
    host: str
    hostname: str
    mesh_ip: str
    port: int
    socket_path: str
    status: str


def load_registry(path: str | None = None) -> dict[str, LangserverEndpoint]:
    """Load lsp-fleet.json → dict keyed by language."""
    p = _find_registry(path)
    data = json.loads(p.read_text())
    out: dict[str, LangserverEndpoint] = {}
    for e in data.get("entries", []):
        out[e["lang"]] = LangserverEndpoint(
            lang=e["lang"],
            host=e["host"],
            hostname=e["hostname"],
            mesh_ip=e["mesh_ip"],
            port=e["port"],
            socket_path=e["socket_path"],
            status=e.get("status", "unknown"),
        )
    return out


# ── LSP JSON-RPC client (raw asyncio, no third-party deps) ───────────────


class LangserverClient:
    """Async LSP client for a single fleet langserver session.

    Usage::

        async with LangserverClient.connect("rust") as lsp:
            await lsp.initialize(root_uri="file:///path/on/mini")
            hover = await lsp.hover("file:///path/on/mini/src/lib.rs", 42, 10)
    """

    def __init__(self, endpoint: LangserverEndpoint, transport: str = "tcp") -> None:
        self._endpoint = endpoint
        self._transport = transport
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._next_id: int = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._read_task: asyncio.Task[None] | None = None
        self._initialized: bool = False

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(
        cls,
        lang: str,
        *,
        transport: str = "tcp",
        registry_path: str | None = None,
    ):
        endpoints = load_registry(registry_path)
        if lang not in endpoints:
            raise KeyError(
                f"no fleet endpoint for lang={lang!r}; known: {sorted(endpoints)}"
            )
        client = cls(endpoints[lang], transport=transport)
        try:
            await client._open()
            yield client
        finally:
            await client._close()

    @property
    def endpoint(self) -> LangserverEndpoint:
        return self._endpoint

    # ── Stream lifecycle ──

    async def _open(self) -> None:
        e = self._endpoint
        if self._transport == "tcp":
            self._reader, self._writer = await asyncio.open_connection(
                host=e.mesh_ip, port=e.port,
            )
        elif self._transport == "unix":
            if not pathlib.Path(e.socket_path).is_socket():
                raise FileNotFoundError(
                    f"Unix socket not present at {e.socket_path} "
                    f"(LSP not running on this host or host={e.host} is remote)"
                )
            self._reader, self._writer = await asyncio.open_unix_connection(
                path=e.socket_path,
            )
        else:
            raise ValueError(f"unknown transport: {self._transport!r}")

        self._read_task = asyncio.create_task(self._read_loop())
        _log.info(
            "langserver_client: connected lang=%s transport=%s endpoint=%s:%d",
            e.lang, self._transport, e.mesh_ip if self._transport == "tcp" else e.socket_path, e.port,
        )

    async def _close(self) -> None:
        if self._initialized:
            with contextlib.suppress(Exception):
                await self.shutdown()
        if self._writer:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
        if self._read_task:
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._read_task

    # ── LSP framing ──

    async def _read_loop(self) -> None:
        assert self._reader is not None
        while True:
            try:
                header = b""
                while not header.endswith(b"\r\n\r\n"):
                    chunk = await self._reader.read(1)
                    if not chunk:
                        return
                    header += chunk
                content_length: int | None = None
                for line in header.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        content_length = int(line.split(b":", 1)[1].strip())
                if content_length is None:
                    raise ValueError("missing Content-Length in LSP response header")
                body = await self._reader.readexactly(content_length)
                msg = json.loads(body)
                rid = msg.get("id")
                if rid is not None and rid in self._pending:
                    fut = self._pending.pop(rid)
                    if "error" in msg:
                        fut.set_exception(RuntimeError(f"LSP error: {msg['error']!r}"))
                    else:
                        fut.set_result(msg.get("result"))
                else:
                    # notification or unsolicited — log and drop for now
                    _log.debug("langserver_client: incoming notification %s", msg.get("method"))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                _log.exception("langserver_client: read loop error")
                return

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        assert self._writer is not None
        self._next_id += 1
        rid = self._next_id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        body = json.dumps(msg).encode("utf-8")
        framed = b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = fut
        self._writer.write(framed)
        await self._writer.drain()
        return await asyncio.wait_for(fut, timeout=30.0)

    async def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        assert self._writer is not None
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        body = json.dumps(msg).encode("utf-8")
        framed = b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        self._writer.write(framed)
        await self._writer.drain()

    # ── LSP method helpers ──

    async def initialize(self, *, root_uri: str | None = None, capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self._request(
            "initialize",
            {
                "processId": None,
                "rootUri": root_uri,
                "capabilities": capabilities or {},
                "clientInfo": {"name": "etzhayyim-langserver-client", "version": "0.1.0"},
            },
        )
        await self._notify("initialized", {})
        self._initialized = True
        return result

    async def shutdown(self) -> None:
        await self._request("shutdown")
        await self._notify("exit")
        self._initialized = False

    async def hover(self, uri: str, line: int, character: int) -> Any:
        return await self._request(
            "textDocument/hover",
            {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}},
        )

    async def definition(self, uri: str, line: int, character: int) -> Any:
        return await self._request(
            "textDocument/definition",
            {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}},
        )

    async def references(self, uri: str, line: int, character: int, *, include_declaration: bool = True) -> Any:
        return await self._request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_declaration},
            },
        )

    async def rename(self, uri: str, line: int, character: int, new_name: str) -> Any:
        return await self._request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "newName": new_name,
            },
        )
