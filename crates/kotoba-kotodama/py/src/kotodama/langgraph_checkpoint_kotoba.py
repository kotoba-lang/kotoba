"""
kotoba-native LangGraph BaseCheckpointSaver (ADR-2605262130 + ADR-2605312345).

RW-free replacement for ``langgraph_checkpoint_rw.RisingWaveCheckpointSaver``.
State lives in the kotoba Datom log (content-addressed EAVT), reached via
``kotodama.kotoba_datomic.KotobaDatomicClient`` — no psycopg, no RisingWave.

The legacy 3-table model maps directly onto namespaced entities:

  vertex_langgraph_checkpoint        → ``:lg.checkpoint/*``        (pointer, vertex-id = pk)
  vertex_langgraph_checkpoint_blob   → ``:lg.checkpoint-blob/*``   (content-addressed, vertex-id = sha256 cid)
  vertex_langgraph_checkpoint_write  → ``:lg.checkpoint-write/*``  (pending writes, vertex-id = pk)

The blob entity is keyed by the content CID (``:db.unique/identity``) so kotoba's
content-addressed store dedups identical checkpoints for free — the same property
the RW saver emulated with "PK implicit upsert".

Datalog ordering/limit is not relied on: per-thread checkpoint sets are small, so
``alist`` pulls the thread's entities and sorts/limits in Python (checkpoint_id is
a monotonic ULID-like string, so lexical DESC = newest first).

The kotoba client is synchronous (urllib); async methods run it via
``asyncio.to_thread`` so the event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import zlib
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator, Sequence

from kotodama.kotoba_datomic import (
    KotobaDatomicClient,
    edn_str,
    get_kotoba_client,
    to_tx_edn,
)

# Shannon source-coding threshold (identical to the RW saver) — below ~2KiB,
# base64 inflation defeats zlib gain on JSON; keep payload plaintext.
_COMPRESS_MIN_BYTES = 2048
_COMPRESS_LEVEL = 6

try:
    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.base import (
        BaseCheckpointSaver,
        ChannelVersions,
        Checkpoint,
        CheckpointMetadata,
        CheckpointTuple,
        PendingWrite,
        get_checkpoint_id,
    )
    _LG_CHECKPOINT_OK = True
except (ImportError, SystemError):  # pragma: no cover — langgraph runtime dep / broken transitive dep
    _LG_CHECKPOINT_OK = False
    RunnableConfig = dict  # type: ignore[assignment,misc]
    BaseCheckpointSaver = object  # type: ignore[assignment,misc]
    ChannelVersions = dict  # type: ignore[assignment]
    Checkpoint = dict  # type: ignore[assignment]
    CheckpointMetadata = dict  # type: ignore[assignment]
    CheckpointTuple = object  # type: ignore[assignment]
    PendingWrite = object  # type: ignore[assignment]

    def get_checkpoint_id(config: Any) -> str | None:  # type: ignore[misc]
        return None

LOG = logging.getLogger(__name__)

CHECKPOINT_GRAPH = os.environ.get("KOTODAMA_KOTOBA_LG_GRAPH", "etzhayyim/kotoba-kotodama/langgraph")

# attribute namespaces
NS_CP = "lg.checkpoint"
NS_BLOB = "lg.checkpoint-blob"
NS_WRITE = "lg.checkpoint-write"


# ─────────────────────────── pure helpers (langgraph-free, testable) ───────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checkpoint_pk(thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
    return f"{thread_id}:{checkpoint_ns}:{checkpoint_id}"


def _write_pk(thread_id: str, checkpoint_ns: str, checkpoint_id: str, task_id: str, idx: int) -> str:
    return f"{thread_id}:{checkpoint_ns}:{checkpoint_id}:{task_id}:{idx}"


def _pack(checkpoint: Any, metadata: Any) -> tuple[str, str, str, int, int]:
    """Serialize + (optionally) compress + content-address.

    Returns (stored_blob, content_cid, compression, logical_bytes, stored_bytes).
    Identical scheme to the RW saver so blobs are interchangeable.
    """
    plain = json.dumps(
        {"checkpoint": checkpoint, "metadata": metadata},
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    raw = plain.encode("utf-8")
    logical = len(raw)
    cid = hashlib.sha256(raw).hexdigest()
    if logical >= _COMPRESS_MIN_BYTES:
        comp = base64.b64encode(zlib.compress(raw, _COMPRESS_LEVEL)).decode("ascii")
        if len(comp) < logical:
            return comp, cid, "zlib-b64", logical, len(comp)
    return plain, cid, "none", logical, logical


def _unpack(blob: str, compression: str | None) -> tuple[Any, Any]:
    if compression == "zlib-b64":
        raw = zlib.decompress(base64.b64decode(blob.encode("ascii")))
        d = json.loads(raw.decode("utf-8"))
    else:
        d = json.loads(blob)
    return d["checkpoint"], d.get("metadata", {})


def _blob_entity(content_cid: str, blob: str, compression: str, logical: int, stored: int, now: str) -> dict[str, Any]:
    return {
        f":{NS_BLOB}/vertex-id": content_cid,
        f":{NS_BLOB}/blob": blob,
        f":{NS_BLOB}/compression": compression,
        f":{NS_BLOB}/blob-size-bytes": logical,
        f":{NS_BLOB}/blob-stored-bytes": stored,
        f":{NS_BLOB}/first-seen-at": now,
    }


def _checkpoint_entity(
    pk: str, thread_id: str, checkpoint_id: str, checkpoint_ns: str,
    parent_checkpoint_id: str | None, content_cid: str, compression: str, logical: int, now: str,
) -> dict[str, Any]:
    ent = {
        f":{NS_CP}/vertex-id": pk,
        f":{NS_CP}/thread-id": thread_id,
        f":{NS_CP}/checkpoint-id": checkpoint_id,
        f":{NS_CP}/checkpoint-ns": checkpoint_ns,
        f":{NS_CP}/content-cid": content_cid,
        f":{NS_CP}/compression": compression,
        f":{NS_CP}/blob-size-bytes": logical,
        f":{NS_CP}/created-at": now,
    }
    if parent_checkpoint_id:
        ent[f":{NS_CP}/parent-checkpoint-id"] = parent_checkpoint_id
    return ent


def _write_entity(
    pk: str, thread_id: str, checkpoint_id: str, checkpoint_ns: str,
    task_id: str, task_path: str, idx: int, channel: str, blob: str, now: str,
) -> dict[str, Any]:
    return {
        f":{NS_WRITE}/vertex-id": pk,
        f":{NS_WRITE}/thread-id": thread_id,
        f":{NS_WRITE}/checkpoint-id": checkpoint_id,
        f":{NS_WRITE}/checkpoint-ns": checkpoint_ns,
        f":{NS_WRITE}/task-id": task_id,
        f":{NS_WRITE}/task-path": task_path,
        f":{NS_WRITE}/idx": idx,
        f":{NS_WRITE}/channel": channel,
        f":{NS_WRITE}/type": "json",
        f":{NS_WRITE}/blob": blob,
        f":{NS_WRITE}/created-at": now,
    }


def _pull_by_attr_query(ns: str, attr: str, value: str) -> str:
    """``[:find (pull ?e [*]) :where [?e :ns/attr "value"]]``."""
    return f"[:find (pull ?e [*]) :where [?e :{ns}/{attr} {edn_str(value)}]]"


def _strip_ns(ent: Any, ns: str) -> dict[str, Any]:
    """``{:lg.checkpoint/thread-id "T"}`` → ``{"thread_id": "T"}`` (kebab→snake)."""
    prefix = f":{ns}/"
    out: dict[str, Any] = {}
    if not isinstance(ent, dict):
        return out
    for k, v in ent.items():
        key = str(k)
        col = key[len(prefix):] if key.startswith(prefix) else key.lstrip(":")
        out[col.replace("-", "_")] = v
    return out


# ─────────────────────────── saver ───────────────────────────

class KotobaCheckpointSaver(BaseCheckpointSaver):
    """LangGraph checkpointer backed by the kotoba Datom log."""

    def __init__(self, client: KotobaDatomicClient | None = None) -> None:
        super().__init__()
        self._client = client or get_kotoba_client()
        self._graph = CHECKPOINT_GRAPH

    # -- client helpers (sync calls off the event loop) --
    async def _transact(self, entities: list[dict[str, Any]], note: str) -> None:
        tx = to_tx_edn(entities, [note])
        await asyncio.to_thread(self._client.transact, tx, graph=self._graph)

    async def _q(self, query_edn: str) -> list[Any]:
        return await asyncio.to_thread(self._client.q, query_edn, graph=self._graph)

    def _config_to_parts(self, config: Any) -> tuple[str, str, str | None]:
        cfg = config.get("configurable", {})
        return (
            cfg.get("thread_id", ""),
            cfg.get("checkpoint_ns", ""),
            cfg.get("checkpoint_id") or get_checkpoint_id(config),
        )

    async def _load_blob(self, content_cid: str) -> tuple[str | None, str | None]:
        rows = await self._q(_pull_by_attr_query(NS_BLOB, "vertex-id", content_cid))
        for item in rows:
            ent = _strip_ns(item[0] if isinstance(item, (list, tuple)) and item else item, NS_BLOB)
            if ent:
                return ent.get("blob"), ent.get("compression")
        return None, None

    # ------------------------------------------------------------------ reads
    async def aget_tuple(self, config: Any) -> Any:
        thread_id, checkpoint_ns, checkpoint_id = self._config_to_parts(config)
        if not thread_id:
            return None
        rows = await self._q(_pull_by_attr_query(NS_CP, "thread-id", thread_id))
        cps = [_strip_ns(it[0] if isinstance(it, (list, tuple)) and it else it, NS_CP) for it in rows]
        cps = [c for c in cps if c.get("checkpoint_ns", "") == checkpoint_ns]
        if checkpoint_id:
            cps = [c for c in cps if c.get("checkpoint_id") == checkpoint_id]
        if not cps:
            return None
        cps.sort(key=lambda c: c.get("checkpoint_id", ""), reverse=True)
        return await self._row_to_tuple(cps[0], config)

    async def alist(
        self,
        config: Any | None,
        *,
        filter: dict[str, Any] | None = None,
        before: Any | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Any]:
        thread_id = (config or {}).get("configurable", {}).get("thread_id", "")
        if not thread_id:
            return
        before_id = (before or {}).get("configurable", {}).get("checkpoint_id")
        rows = await self._q(_pull_by_attr_query(NS_CP, "thread-id", thread_id))
        cps = [_strip_ns(it[0] if isinstance(it, (list, tuple)) and it else it, NS_CP) for it in rows]
        if before_id:
            cps = [c for c in cps if c.get("checkpoint_id", "") < before_id]
        cps.sort(key=lambda c: c.get("checkpoint_id", ""), reverse=True)
        if limit:
            cps = cps[: int(limit)]
        for cp in cps:
            yield await self._row_to_tuple(cp, config or {})

    async def _row_to_tuple(self, cp: dict[str, Any], config: Any) -> Any:
        thread_id = cp.get("thread_id", "")
        checkpoint_ns = cp.get("checkpoint_ns", "")
        checkpoint_id = cp.get("checkpoint_id", "")
        blob, compression = await self._load_blob(cp.get("content_cid", ""))
        if blob is None:
            return None
        checkpoint, metadata = _unpack(blob, compression)
        parent_config = None
        if cp.get("parent_checkpoint_id"):
            parent_config = {"configurable": {
                "thread_id": thread_id, "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": cp["parent_checkpoint_id"],
            }}
        pending_writes = await self._load_writes(thread_id, checkpoint_ns, checkpoint_id)
        return CheckpointTuple(
            config={"configurable": {
                "thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id,
            }},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def _load_writes(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> list[Any]:
        rows = await self._q(_pull_by_attr_query(NS_WRITE, "checkpoint-id", checkpoint_id))
        writes = [_strip_ns(it[0] if isinstance(it, (list, tuple)) and it else it, NS_WRITE) for it in rows]
        writes = [w for w in writes if w.get("thread_id") == thread_id and w.get("checkpoint_ns", "") == checkpoint_ns]
        writes.sort(key=lambda w: int(w.get("idx", 0)))
        return [
            (w.get("task_id", ""), w.get("channel", ""),
             json.loads(w["blob"]) if w.get("type") == "json" else w.get("blob"))
            for w in writes
        ]

    # ----------------------------------------------------------------- writes
    async def aput(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        thread_id, checkpoint_ns, _ = self._config_to_parts(config)
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = (config.get("configurable") or {}).get("checkpoint_id")
        pk = _checkpoint_pk(thread_id, checkpoint_ns, checkpoint_id)
        blob, content_cid, compression, logical, stored = _pack(checkpoint, metadata)
        now = _now()
        # blob (content-addressed, dedups) + pointer in one transaction
        await self._transact(
            [
                _blob_entity(content_cid, blob, compression, logical, stored, now),
                _checkpoint_entity(pk, thread_id, checkpoint_id, checkpoint_ns,
                                   parent_checkpoint_id, content_cid, compression, logical, now),
            ],
            f"langgraph checkpoint {pk}",
        )
        return {"configurable": {
            "thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id,
        }}

    async def aput_writes(
        self, config: Any, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "",
    ) -> None:
        thread_id, checkpoint_ns, checkpoint_id = self._config_to_parts(config)
        if not checkpoint_id:
            return
        now = _now()
        ents = []
        for idx, (channel, value) in enumerate(writes):
            pk = _write_pk(thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            ents.append(_write_entity(
                pk, thread_id, checkpoint_id, checkpoint_ns, task_id, task_path, idx,
                channel, json.dumps(value, default=str), now,
            ))
        if ents:
            await self._transact(ents, f"langgraph writes {checkpoint_id}/{task_id}")

    # --------------------------------------------------------------- deletion
    async def adelete_thread(self, thread_id: str) -> None:
        # Datom log is append-only history (非終末論); retraction marks tombstones.
        # We retract the identity of every checkpoint + write entity for the thread.
        retracts: list[dict[str, Any]] = []
        for ns in (NS_CP, NS_WRITE):
            rows = await self._q(_pull_by_attr_query(ns, "thread-id", thread_id))
            for it in rows:
                ent = _strip_ns(it[0] if isinstance(it, (list, tuple)) and it else it, ns)
                vid = ent.get("vertex_id")
                if vid:
                    retracts.append({f":{ns}/vertex-id": vid, ":db/retractEntity": True})
        if retracts:
            await self._transact(retracts, f"retract thread {thread_id}")

    # --------------------------------------------------------- version counter
    def get_next_version(self, current: int | None, channel: Any) -> int:
        return (current or 0) + 1

    # ---------------------------------------------------- sync fallback shims
    def get_tuple(self, config: Any) -> Any:
        return asyncio.get_event_loop().run_until_complete(self.aget_tuple(config))

    def list(self, config: Any | None, *, filter=None, before=None, limit=None) -> Iterator[Any]:  # noqa: ANN001
        async def _collect() -> list[Any]:
            return [t async for t in self.alist(config, filter=filter, before=before, limit=limit)]
        yield from asyncio.get_event_loop().run_until_complete(_collect())

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        return asyncio.get_event_loop().run_until_complete(self.aput(config, checkpoint, metadata, new_versions))

    def put_writes(self, config: Any, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        asyncio.get_event_loop().run_until_complete(self.aput_writes(config, writes, task_id, task_path))


_SAVER_INSTANCE: KotobaCheckpointSaver | None = None


async def get_checkpoint_saver() -> KotobaCheckpointSaver:
    """Return (or create) the process-level singleton kotoba checkpoint saver."""
    global _SAVER_INSTANCE
    if _SAVER_INSTANCE is None:
        _SAVER_INSTANCE = KotobaCheckpointSaver()
    return _SAVER_INSTANCE
