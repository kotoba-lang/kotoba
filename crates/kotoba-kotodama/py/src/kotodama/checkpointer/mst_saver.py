"""MstCheckpointSaver — LangGraph BaseCheckpointSaver over an IPC socket.

Wire protocol authoritative per ADR-2605171800 §Stage 1:

  Request  := { v: 1, op, cell_did, thread_id, checkpoint_ns,
                checkpoint_id, payload, meta }
  Response := { ok, mst_root_cid, data, error }

Framing: 4-byte big-endian length prefix, then msgpack body. Same on
both sides. Default transport is a Unix-domain SOCK_STREAM at
``/run/etzhayyim/checkpointer.sock``; a ``tcp://host:port`` socket path
selects TCP instead (for test rigs that run the sidecar out-of-host).

All MST / IPFS / viem code lives in the TS sidecar
(``@etzhayyim/sdk/checkpointer``). This module holds no substrate
logic; per ADR-2605172100 substrate client imports flow only through
``@etzhayyim/sdk``.

Implementation scope:
  - Sync methods (``put``, ``get_tuple``, ``list``, ``put_writes``)
  - Async counterparts (``aput``, ``aget_tuple``, ``alist``,
    ``aput_writes``) over asyncio streams.
  - Lazy persistent connections per (sync, async) class.
  - Health check (``op="health"``) used to validate the sidecar before
    a graph compile.

Out of scope (delegated to the sidecar):
  - MST construction and CAR encoding (Stage 2)
  - IPFS pinning (Stage 3)
  - L2 anchor batching (Stage 4)
"""
from __future__ import annotations

import asyncio
import socket
import struct
import threading
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

try:
    import msgpack  # type: ignore[import-not-found]
except ImportError as exc:  # pragma: no cover — surfaced at import time
    raise ImportError(
        "MstCheckpointSaver requires msgpack. Install: pip install msgpack"
    ) from exc

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

MST_CHECKPOINT_PROTOCOL_VERSION = 1
DEFAULT_SOCKET_PATH = "/run/etzhayyim/checkpointer.sock"
DEFAULT_CONNECT_TIMEOUT_SEC = 5.0
DEFAULT_CALL_TIMEOUT_SEC = 30.0

_LEN_PREFIX_BYTES = 4
_LEN_PREFIX_STRUCT = struct.Struct(">I")  # 4-byte big-endian unsigned


class MstCheckpointSaverError(RuntimeError):
    """Sidecar returned ``ok=False`` or the socket closed unexpectedly."""


class MstCheckpointSaverProtocolError(MstCheckpointSaverError):
    """Sidecar response failed wire-protocol validation."""


# ── Framing primitives ───────────────────────────────────────────────────────


def _pack_request(req: dict[str, Any]) -> bytes:
    body = msgpack.packb(req, use_bin_type=True)
    return _LEN_PREFIX_STRUCT.pack(len(body)) + body


def _decode_response(body: bytes) -> dict[str, Any]:
    resp = msgpack.unpackb(body, raw=False)
    if not isinstance(resp, dict):
        raise MstCheckpointSaverProtocolError(
            f"response is not a dict: {type(resp).__name__}"
        )
    if "ok" not in resp:
        raise MstCheckpointSaverProtocolError(
            "response missing required 'ok' field"
        )
    return resp


# ── Sync transport ───────────────────────────────────────────────────────────


class _SyncClient:
    """Single persistent sync connection, guarded by a lock."""

    def __init__(self, socket_path: str, connect_timeout: float, call_timeout: float):
        self._socket_path = socket_path
        self._connect_timeout = connect_timeout
        self._call_timeout = call_timeout
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            sock = self._ensure_open()
            try:
                sock.sendall(_pack_request(request))
                head = self._recv_exact(sock, _LEN_PREFIX_BYTES)
                (length,) = _LEN_PREFIX_STRUCT.unpack(head)
                body = self._recv_exact(sock, length)
            except (OSError, MstCheckpointSaverProtocolError):
                # Drop the bad socket so the next call reconnects.
                self._close_locked()
                raise
            return _decode_response(body)

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    # ── helpers (caller holds self._lock) ─────────────────────────────────

    def _ensure_open(self) -> socket.socket:
        if self._sock is not None:
            return self._sock
        if self._socket_path.startswith("tcp://"):
            host, _, port_str = self._socket_path[len("tcp://"):].partition(":")
            if not host or not port_str:
                raise ValueError(
                    f"tcp:// socket_path must be tcp://host:port; got "
                    f"{self._socket_path!r}"
                )
            s = socket.create_connection(
                (host, int(port_str)), timeout=self._connect_timeout
            )
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(self._connect_timeout)
            s.connect(self._socket_path)
        s.settimeout(self._call_timeout)
        self._sock = s
        return s

    def _close_locked(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        buf = bytearray(n)
        view = memoryview(buf)
        got = 0
        while got < n:
            r = sock.recv_into(view[got:])
            if r == 0:
                raise MstCheckpointSaverProtocolError(
                    "sidecar closed connection mid-frame"
                )
            got += r
        return bytes(buf)


# ── Async transport ──────────────────────────────────────────────────────────


class _AsyncClient:
    """Single persistent async connection, guarded by an asyncio.Lock."""

    def __init__(self, socket_path: str, connect_timeout: float, call_timeout: float):
        self._socket_path = socket_path
        self._connect_timeout = connect_timeout
        self._call_timeout = call_timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock: asyncio.Lock | None = None  # created lazily on event loop

    async def call(self, request: dict[str, Any]) -> dict[str, Any]:
        lock = self._get_lock()
        async with lock:
            reader, writer = await self._ensure_open()
            try:
                writer.write(_pack_request(request))
                await asyncio.wait_for(writer.drain(), timeout=self._call_timeout)
                head = await asyncio.wait_for(
                    reader.readexactly(_LEN_PREFIX_BYTES),
                    timeout=self._call_timeout,
                )
                (length,) = _LEN_PREFIX_STRUCT.unpack(head)
                body = await asyncio.wait_for(
                    reader.readexactly(length),
                    timeout=self._call_timeout,
                )
            except (OSError, asyncio.IncompleteReadError, MstCheckpointSaverProtocolError):
                await self._close_locked()
                raise
            return _decode_response(body)

    async def close(self) -> None:
        lock = self._get_lock()
        async with lock:
            await self._close_locked()

    # ── helpers ───────────────────────────────────────────────────────────

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _ensure_open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if self._reader is not None and self._writer is not None:
            return self._reader, self._writer
        if self._socket_path.startswith("tcp://"):
            host, _, port_str = self._socket_path[len("tcp://"):].partition(":")
            if not host or not port_str:
                raise ValueError(
                    f"tcp:// socket_path must be tcp://host:port; got "
                    f"{self._socket_path!r}"
                )
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, int(port_str)),
                timeout=self._connect_timeout,
            )
        else:
            r, w = await asyncio.wait_for(
                asyncio.open_unix_connection(self._socket_path),
                timeout=self._connect_timeout,
            )
        self._reader, self._writer = r, w
        return r, w

    async def _close_locked(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader, self._writer = None, None


# ── Saver ────────────────────────────────────────────────────────────────────


class MstCheckpointSaver(BaseCheckpointSaver):
    """LangGraph BaseCheckpointSaver routing every op to a TS sidecar.

    The sidecar (``@etzhayyim/sdk/checkpointer``) projects each payload to
    an atproto-shaped MST, returns the root CID synchronously on ``put``,
    and asynchronously enqueues an IPFS pin + L2 anchor (Stages 3-4).

    Args:
        cell_did: DID of the cell whose state we're checkpointing. Used
            as the namespace key on the sidecar side; also enforced
            against the sidecar's ``allowedDids`` allowlist.
        socket_path: Unix socket path (``/run/etzhayyim/checkpointer.sock``
            by default) or ``tcp://host:port`` for out-of-host test rigs.
        connect_timeout_sec: Seconds to wait for the initial connection.
        call_timeout_sec: Seconds to wait for each round-trip after
            connection is established.
        serde: Optional serializer override. Defaults to
            ``langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer``.
    """

    def __init__(
        self,
        *,
        cell_did: str,
        socket_path: str = DEFAULT_SOCKET_PATH,
        connect_timeout_sec: float = DEFAULT_CONNECT_TIMEOUT_SEC,
        call_timeout_sec: float = DEFAULT_CALL_TIMEOUT_SEC,
        serde: Any = None,
    ):
        super().__init__(serde=serde)
        if not cell_did or not cell_did.startswith("did:"):
            raise ValueError(
                f"cell_did must be a DID (start with 'did:'); got {cell_did!r}"
            )
        self.cell_did = cell_did
        self.socket_path = socket_path
        self._sync = _SyncClient(socket_path, connect_timeout_sec, call_timeout_sec)
        self._async = _AsyncClient(socket_path, connect_timeout_sec, call_timeout_sec)

    # ── Public ops ────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Send a ``health`` ping. Raises on transport failure."""
        return self._call(self._envelope("health", thread_id="", checkpoint_ns=""))

    async def ahealth(self) -> dict[str, Any]:
        return await self._acall(
            self._envelope("health", thread_id="", checkpoint_ns="")
        )

    def close(self) -> None:
        self._sync.close()

    async def aclose(self) -> None:
        await self._async.close()

    # ── BaseCheckpointSaver: sync ─────────────────────────────────────────

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id, ns, _ = _config_to_ids(config, required_checkpoint_id=False)
        cp_id = checkpoint["id"]
        payload = self._encode_checkpoint(checkpoint, metadata, new_versions)
        envelope = self._envelope(
            "put",
            thread_id=thread_id,
            checkpoint_ns=ns,
            checkpoint_id=cp_id,
            payload=payload,
        )
        self._call(envelope)
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": ns,
                "checkpoint_id": cp_id,
            }
        }

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id, ns, cp_id = _config_to_ids(config, required_checkpoint_id=False)
        envelope = self._envelope(
            "get_tuple",
            thread_id=thread_id,
            checkpoint_ns=ns,
            checkpoint_id=cp_id,  # may be None → sidecar returns latest
        )
        resp = self._call(envelope)
        return self._decode_tuple_response(resp, thread_id=thread_id, ns=ns)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        thread_id, ns = ("", "")
        if config is not None:
            thread_id, ns, _ = _config_to_ids(config, required_checkpoint_id=False)
        meta: dict[str, Any] = {}
        if filter:
            meta["filter"] = filter
        if before is not None:
            _, _, before_id = _config_to_ids(before, required_checkpoint_id=True)
            meta["before_checkpoint_id"] = before_id
        if limit is not None:
            meta["limit"] = int(limit)
        envelope = self._envelope(
            "list",
            thread_id=thread_id,
            checkpoint_ns=ns,
            meta=meta,
        )
        resp = self._call(envelope)
        yield from self._decode_list_response(resp, thread_id=thread_id, ns=ns)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, ns, cp_id = _config_to_ids(config, required_checkpoint_id=True)
        payload = self._encode_writes(writes)
        envelope = self._envelope(
            "put_writes",
            thread_id=thread_id,
            checkpoint_ns=ns,
            checkpoint_id=cp_id,
            payload=payload,
            meta={"task_id": task_id, "task_path": task_path},
        )
        self._call(envelope)

    # ── BaseCheckpointSaver: async ────────────────────────────────────────

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id, ns, _ = _config_to_ids(config, required_checkpoint_id=False)
        cp_id = checkpoint["id"]
        payload = self._encode_checkpoint(checkpoint, metadata, new_versions)
        envelope = self._envelope(
            "put",
            thread_id=thread_id,
            checkpoint_ns=ns,
            checkpoint_id=cp_id,
            payload=payload,
        )
        await self._acall(envelope)
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": ns,
                "checkpoint_id": cp_id,
            }
        }

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id, ns, cp_id = _config_to_ids(config, required_checkpoint_id=False)
        envelope = self._envelope(
            "get_tuple",
            thread_id=thread_id,
            checkpoint_ns=ns,
            checkpoint_id=cp_id,
        )
        resp = await self._acall(envelope)
        return self._decode_tuple_response(resp, thread_id=thread_id, ns=ns)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        thread_id, ns = ("", "")
        if config is not None:
            thread_id, ns, _ = _config_to_ids(config, required_checkpoint_id=False)
        meta: dict[str, Any] = {}
        if filter:
            meta["filter"] = filter
        if before is not None:
            _, _, before_id = _config_to_ids(before, required_checkpoint_id=True)
            meta["before_checkpoint_id"] = before_id
        if limit is not None:
            meta["limit"] = int(limit)
        envelope = self._envelope(
            "list",
            thread_id=thread_id,
            checkpoint_ns=ns,
            meta=meta,
        )
        resp = await self._acall(envelope)
        for tup in self._decode_list_response(resp, thread_id=thread_id, ns=ns):
            yield tup

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, ns, cp_id = _config_to_ids(config, required_checkpoint_id=True)
        payload = self._encode_writes(writes)
        envelope = self._envelope(
            "put_writes",
            thread_id=thread_id,
            checkpoint_ns=ns,
            checkpoint_id=cp_id,
            payload=payload,
            meta={"task_id": task_id, "task_path": task_path},
        )
        await self._acall(envelope)

    # ── Internals ─────────────────────────────────────────────────────────

    def _envelope(
        self,
        op: str,
        *,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str | None = None,
        payload: bytes | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "v": MST_CHECKPOINT_PROTOCOL_VERSION,
            "op": op,
            "cell_did": self.cell_did,
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "payload": payload,
            "meta": meta or {},
        }

    def _call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        resp = self._sync.call(envelope)
        if not resp.get("ok"):
            raise MstCheckpointSaverError(
                f"sidecar op={envelope['op']!r} failed: {resp.get('error')!r}"
            )
        return resp

    async def _acall(self, envelope: dict[str, Any]) -> dict[str, Any]:
        resp = await self._async.call(envelope)
        if not resp.get("ok"):
            raise MstCheckpointSaverError(
                f"sidecar op={envelope['op']!r} failed: {resp.get('error')!r}"
            )
        return resp

    def _encode_checkpoint(
        self,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> bytes:
        type_tag, body = self.serde.dumps_typed(
            (checkpoint, metadata, new_versions)
        )
        return msgpack.packb({"t": type_tag, "b": body}, use_bin_type=True)

    def _encode_writes(self, writes: Sequence[tuple[str, Any]]) -> bytes:
        type_tag, body = self.serde.dumps_typed(list(writes))
        return msgpack.packb({"t": type_tag, "b": body}, use_bin_type=True)

    def _decode_tuple_response(
        self,
        resp: dict[str, Any],
        *,
        thread_id: str,
        ns: str,
    ) -> CheckpointTuple | None:
        data = resp.get("data")
        if not data:
            return None
        meta = resp.get("meta") or {}
        checkpoint_id = meta.get("checkpoint_id") or ""
        parent_id = meta.get("parent_checkpoint_id")
        pending_writes_blob = meta.get("pending_writes_blob")

        wrapper = msgpack.unpackb(data, raw=False)
        if not isinstance(wrapper, dict):
            raise MstCheckpointSaverProtocolError(
                "tuple payload wrapper is not a dict"
            )
        checkpoint, metadata, _new_versions = self.serde.loads_typed(
            (wrapper["t"], wrapper["b"])
        )

        parent_config: RunnableConfig | None = None
        if parent_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": ns,
                    "checkpoint_id": parent_id,
                }
            }

        pending_writes = None
        if pending_writes_blob:
            pending_writes = self.serde.loads_typed(
                (pending_writes_blob["t"], pending_writes_blob["b"])
            )

        config_out: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": ns,
                "checkpoint_id": checkpoint_id or checkpoint["id"],
            }
        }
        return CheckpointTuple(
            config=config_out,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    def _decode_list_response(
        self,
        resp: dict[str, Any],
        *,
        thread_id: str,
        ns: str,
    ) -> Iterator[CheckpointTuple]:
        data = resp.get("data")
        if not data:
            return iter(())
        entries = msgpack.unpackb(data, raw=False)
        if not isinstance(entries, list):
            raise MstCheckpointSaverProtocolError(
                "list payload is not a msgpack list"
            )
        tuples: list[CheckpointTuple] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            sub_thread_id = entry.get("thread_id", thread_id)
            sub_ns = entry.get("checkpoint_ns", ns)
            sub_resp = {
                "data": entry.get("payload"),
                "meta": {
                    "checkpoint_id": entry.get("checkpoint_id"),
                    "parent_checkpoint_id": entry.get("parent_checkpoint_id"),
                    "pending_writes_blob": entry.get("pending_writes_blob"),
                },
            }
            decoded = self._decode_tuple_response(
                sub_resp, thread_id=sub_thread_id, ns=sub_ns
            )
            if decoded is not None:
                tuples.append(decoded)
        return iter(tuples)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _config_to_ids(
    config: RunnableConfig,
    *,
    required_checkpoint_id: bool,
) -> tuple[str, str, str | None]:
    configurable = config.get("configurable") if isinstance(config, dict) else None
    if not isinstance(configurable, dict):
        raise ValueError(
            "MstCheckpointSaver requires config['configurable'] to be a dict"
        )
    thread_id = configurable.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError(
            "MstCheckpointSaver requires config['configurable']['thread_id']"
        )
    ns = configurable.get("checkpoint_ns", "")
    if not isinstance(ns, str):
        raise ValueError("checkpoint_ns must be a string")
    cp_id = configurable.get("checkpoint_id")
    if cp_id is not None and not isinstance(cp_id, str):
        raise ValueError("checkpoint_id must be a string or None")
    if required_checkpoint_id and not cp_id:
        raise ValueError(
            "config['configurable']['checkpoint_id'] is required for this op"
        )
    return thread_id, ns, cp_id
