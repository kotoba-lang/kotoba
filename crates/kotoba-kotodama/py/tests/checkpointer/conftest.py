"""Mock sidecar fixture — a TCP echo of the MstCheckpointSaver wire protocol.

A real sidecar lives in ``20-actors/etzhayyim-sdk/dist/checkpointer.js``.
For unit tests we run an asyncio TCP server in a thread that speaks the
same 4-byte-prefix + msgpack framing and stores per-(thread, ns) the
last payload, exposing the same op set documented in ADR-2605171800.
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Generator
from contextlib import suppress
from typing import Any

import msgpack
import pytest


_LEN_PREFIX_BYTES = 4


class _Frame:
    @staticmethod
    def pack(body: bytes) -> bytes:
        return len(body).to_bytes(_LEN_PREFIX_BYTES, "big") + body

    @staticmethod
    async def read_one(reader: asyncio.StreamReader) -> dict[str, Any]:
        head = await reader.readexactly(_LEN_PREFIX_BYTES)
        n = int.from_bytes(head, "big")
        body = await reader.readexactly(n)
        return msgpack.unpackb(body, raw=False)


class MockSidecar:
    """In-memory TCP sidecar. Records every received request for assertion."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], bytes] = {}
        # Per (thread, ns) → list[(checkpoint_id, parent_checkpoint_id)]
        # in insertion order so list() can return newest-first.
        self._order: dict[tuple[str, str], list[tuple[str, str | None]]] = {}
        self._writes: dict[tuple[str, str, str], list[bytes]] = {}
        self._fail_next_op: str | None = None
        self.requests: list[dict[str, Any]] = []
        self.port: int | None = None
        self._server: asyncio.AbstractServer | None = None
        self._stop_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    # ── lifecycle ──

    def start(self) -> None:
        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._serve())
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise TimeoutError("MockSidecar failed to start within 5s")

    def stop(self) -> None:
        if self._loop is not None and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    @property
    def url(self) -> str:
        assert self.port is not None, "MockSidecar.start() must be called first"
        return f"tcp://127.0.0.1:{self.port}"

    # ── test hooks ──

    def fail_next(self, op: str) -> None:
        """Make the next handled request with op==`op` return ok=False."""
        self._fail_next_op = op

    def snapshot(self) -> dict[tuple[str, str, str], bytes]:
        return dict(self._store)

    # ── handler ──

    async def _serve(self) -> None:
        server = await asyncio.start_server(self._handle, host="127.0.0.1", port=0)
        self._server = server
        self._stop_event = asyncio.Event()
        # type: ignore[index] — sockets attribute is always populated for an IP server
        self.port = server.sockets[0].getsockname()[1]
        self._ready.set()
        try:
            await self._stop_event.wait()
        finally:
            server.close()
            with suppress(Exception):
                await server.wait_closed()

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            while True:
                try:
                    req = await _Frame.read_one(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    return
                self.requests.append(req)
                resp = self._dispatch(req)
                writer.write(_Frame.pack(msgpack.packb(resp, use_bin_type=True)))
                await writer.drain()
        finally:
            with suppress(Exception):
                writer.close()
                await writer.wait_closed()

    def _dispatch(self, req: dict[str, Any]) -> dict[str, Any]:
        if req.get("v") != 1:
            return _err("protocol version mismatch")
        op = req.get("op")
        if op == self._fail_next_op:
            self._fail_next_op = None
            return _err(f"injected failure for op={op}")

        if op == "health":
            return _ok()
        if op == "put":
            return self._handle_put(req)
        if op == "get_tuple":
            return self._handle_get_tuple(req)
        if op == "list":
            return self._handle_list(req)
        if op == "put_writes":
            return self._handle_put_writes(req)
        return _err(f"unknown op: {op!r}")

    def _handle_put(self, req: dict[str, Any]) -> dict[str, Any]:
        thread_id = req["thread_id"]
        ns = req["checkpoint_ns"]
        cp_id = req["checkpoint_id"]
        payload = req["payload"]
        if not isinstance(cp_id, str) or not cp_id:
            return _err("put: checkpoint_id required")
        order = self._order.setdefault((thread_id, ns), [])
        parent_id = order[-1][0] if order else None
        order.append((cp_id, parent_id))
        self._store[(thread_id, ns, cp_id)] = payload
        return _ok(mst_root_cid=f"bafy-mock-{cp_id[:8]}")

    def _handle_get_tuple(self, req: dict[str, Any]) -> dict[str, Any]:
        thread_id = req["thread_id"]
        ns = req["checkpoint_ns"]
        cp_id = req.get("checkpoint_id")
        order = self._order.get((thread_id, ns), [])
        if not order:
            return _ok(data=None)
        if cp_id is None:
            cp_id, parent_id = order[-1]
        else:
            try:
                idx = next(i for i, (cid, _) in enumerate(order) if cid == cp_id)
            except StopIteration:
                return _ok(data=None)
            parent_id = order[idx - 1][0] if idx > 0 else None
        payload = self._store.get((thread_id, ns, cp_id))
        if payload is None:
            return _ok(data=None)
        return _ok(
            data=payload,
            meta={
                "checkpoint_id": cp_id,
                "parent_checkpoint_id": parent_id,
            },
        )

    def _handle_list(self, req: dict[str, Any]) -> dict[str, Any]:
        thread_id = req["thread_id"]
        ns = req["checkpoint_ns"]
        meta = req.get("meta") or {}
        before = meta.get("before_checkpoint_id")
        limit = meta.get("limit")
        order = list(reversed(self._order.get((thread_id, ns), [])))
        if before:
            order = [pair for pair in order if pair[0] < before]
        if isinstance(limit, int) and limit > 0:
            order = order[:limit]
        entries = [
            {
                "thread_id": thread_id,
                "checkpoint_ns": ns,
                "checkpoint_id": cp_id,
                "parent_checkpoint_id": parent_id,
                "payload": self._store.get((thread_id, ns, cp_id)),
            }
            for cp_id, parent_id in order
        ]
        return _ok(data=msgpack.packb(entries, use_bin_type=True))

    def _handle_put_writes(self, req: dict[str, Any]) -> dict[str, Any]:
        key = (req["thread_id"], req["checkpoint_ns"], req["checkpoint_id"])
        self._writes.setdefault(key, []).append(req["payload"])
        return _ok()


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "mst_root_cid": kwargs.get("mst_root_cid"),
        "data": kwargs.get("data"),
        "error": None,
        "meta": kwargs.get("meta"),
    }


def _err(msg: str) -> dict[str, Any]:
    return {
        "ok": False,
        "mst_root_cid": None,
        "data": None,
        "error": msg,
    }


@pytest.fixture
def mock_sidecar() -> Generator[MockSidecar, None, None]:
    sidecar = MockSidecar()
    sidecar.start()
    try:
        yield sidecar
    finally:
        sidecar.stop()
