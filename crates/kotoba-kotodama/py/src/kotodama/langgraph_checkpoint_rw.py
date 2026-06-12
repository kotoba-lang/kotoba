"""
RisingWave-native LangGraph BaseCheckpointSaver (ADR-2605080600).

RisingWave 制約への対応:
  - FOR UPDATE SKIP LOCKED なし → 不要 (single-flight は actor レベルの lock で保証)
  - LISTEN/NOTIFY なし          → polling (ORDER BY checkpoint_id DESC LIMIT 1)
  - ON CONFLICT なし            → PK overwrite (RW の implicit upsert)
  - multi-statement TX なし     → autocommit=True
  - LIMIT はパラメータ不可      → f-string int (rw-psycopg3-no-param-limit)

Tables:
  vertex_langgraph_checkpoint        — checkpoint本体 (既存)
  vertex_langgraph_checkpoint_write  — pending writes (新規, migration 20260507600000)

vertex_id PK format:
  checkpoint : "{thread_id}:{checkpoint_ns}:{checkpoint_id}"
  write      : "{thread_id}:{checkpoint_ns}:{checkpoint_id}:{task_id}:{idx}"
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import zlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator, Sequence

# Shannon source-coding threshold. Below this (~ 2KiB), base64 inflation
# defeats zlib gain on JSON; keep payload as plaintext.
_COMPRESS_MIN_BYTES = 2048
_COMPRESS_LEVEL = 6  # zlib level: balance latency vs ratio

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
except ImportError:  # pragma: no cover — langgraph is a runtime dep
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

from kotodama.rw_async_pool import ensure_rw_async_pool as _ensure_pool


@asynccontextmanager
async def _cursor():
    p = await _ensure_pool()
    async with p.connection() as conn:
        async with conn.cursor() as cur:
            yield cur


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checkpoint_pk(thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
    return f"{thread_id}:{checkpoint_ns}:{checkpoint_id}"


def _write_pk(thread_id: str, checkpoint_ns: str, checkpoint_id: str, task_id: str, idx: int) -> str:
    return f"{thread_id}:{checkpoint_ns}:{checkpoint_id}:{task_id}:{idx}"


def _config_to_parts(config: RunnableConfig) -> tuple[str, str, str | None]:
    cfg = config.get("configurable", {})
    thread_id: str = cfg.get("thread_id", "")
    checkpoint_ns: str = cfg.get("checkpoint_ns", "")
    checkpoint_id: str | None = cfg.get("checkpoint_id") or get_checkpoint_id(config)
    return thread_id, checkpoint_ns, checkpoint_id


def _pack(checkpoint: Checkpoint, metadata: CheckpointMetadata) -> tuple[str, str, str, int, int]:
    """Serialize + (optionally) compress + content-address.

    Returns (stored_blob, content_cid, compression, logical_bytes, stored_bytes).
    `compression` ∈ {"none", "zlib-b64"}. `content_cid` = sha256(canonical-json).
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


def _unpack(blob: str, compression: str | None) -> tuple[Checkpoint, CheckpointMetadata]:
    if compression == "zlib-b64":
        raw = zlib.decompress(base64.b64decode(blob.encode("ascii")))
        d = json.loads(raw.decode("utf-8"))
    else:
        d = json.loads(blob)
    return d["checkpoint"], d.get("metadata", {})


class RisingWaveCheckpointSaver(BaseCheckpointSaver):
    """LangGraph checkpointer backed by RisingWave vertex_langgraph_checkpoint."""

    # ------------------------------------------------------------------ reads

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id, checkpoint_ns, checkpoint_id = _config_to_parts(config)
        if not thread_id:
            return None
        async with _cursor() as cur:
            if checkpoint_id:
                pk = _checkpoint_pk(thread_id, checkpoint_ns, checkpoint_id)
                await cur.execute(
                    "SELECT c.vertex_id, c.thread_id, c.checkpoint_id, c.checkpoint_ns, "
                    "c.parent_checkpoint_id, c.checkpoint_type, "
                    "COALESCE(NULLIF(c.blob, ''), b.blob) AS blob, "
                    "COALESCE(b.compression, c.compression) AS compression "
                    "FROM vertex_langgraph_checkpoint c "
                    "LEFT JOIN vertex_langgraph_checkpoint_blob b "
                    "  ON b.vertex_id = c.content_cid "
                    "WHERE c.vertex_id = %s",
                    (pk,),
                )
            else:
                await cur.execute(
                    "SELECT c.vertex_id, c.thread_id, c.checkpoint_id, c.checkpoint_ns, "
                    "c.parent_checkpoint_id, c.checkpoint_type, "
                    "COALESCE(NULLIF(c.blob, ''), b.blob) AS blob, "
                    "COALESCE(b.compression, c.compression) AS compression "
                    "FROM vertex_langgraph_checkpoint c "
                    "LEFT JOIN vertex_langgraph_checkpoint_blob b "
                    "  ON b.vertex_id = c.content_cid "
                    f"WHERE c.thread_id = %s AND c.checkpoint_ns = %s "
                    f"ORDER BY c.checkpoint_id DESC LIMIT 1",
                    (thread_id, checkpoint_ns),
                )
            row = await cur.fetchone()
        if row is None:
            return None
        return await self._row_to_tuple(row, config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        thread_id = (config or {}).get("configurable", {}).get("thread_id", "")
        if not thread_id:
            return
        before_id = (before or {}).get("configurable", {}).get("checkpoint_id")
        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        before_clause = "AND checkpoint_id < %s" if before_id else ""
        params: list[Any] = [thread_id]
        if before_id:
            params.append(before_id)
        async with _cursor() as cur:
            await cur.execute(
                f"SELECT c.vertex_id, c.thread_id, c.checkpoint_id, c.checkpoint_ns, "
                f"c.parent_checkpoint_id, c.checkpoint_type, "
                f"COALESCE(NULLIF(c.blob, ''), b.blob) AS blob, "
                f"COALESCE(b.compression, c.compression) AS compression "
                f"FROM vertex_langgraph_checkpoint c "
                f"LEFT JOIN vertex_langgraph_checkpoint_blob b "
                f"  ON b.vertex_id = c.content_cid "
                f"WHERE c.thread_id = %s {before_clause.replace('checkpoint_id', 'c.checkpoint_id')} "
                f"ORDER BY c.checkpoint_id DESC {limit_clause}",
                params,
            )
            rows = await cur.fetchall()
        for row in rows:
            yield await self._row_to_tuple(row, config or {})

    async def _row_to_tuple(self, row: Any, config: RunnableConfig) -> CheckpointTuple:
        (vertex_id, thread_id, checkpoint_id, checkpoint_ns,
         parent_checkpoint_id, _checkpoint_type, blob, compression) = row
        checkpoint, metadata = _unpack(blob, compression)
        parent_config: RunnableConfig | None = None
        if parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_checkpoint_id,
                }
            }
        pending_writes = await self._load_writes(thread_id, checkpoint_ns, checkpoint_id)
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def _load_writes(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> list[PendingWrite]:
        async with _cursor() as cur:
            await cur.execute(
                "SELECT task_id, channel, type, blob "
                "FROM vertex_langgraph_checkpoint_write "
                "WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s "
                "ORDER BY idx ASC",
                (thread_id, checkpoint_ns, checkpoint_id),
            )
            rows = await cur.fetchall()
        return [
            (task_id, channel, json.loads(blob) if type_ == "json" else blob)
            for task_id, channel, type_, blob in rows
        ]

    # ----------------------------------------------------------------- writes

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id, checkpoint_ns, _ = _config_to_parts(config)
        checkpoint_id: str = checkpoint["id"]
        parent_checkpoint_id: str | None = (config.get("configurable") or {}).get("checkpoint_id")
        pk = _checkpoint_pk(thread_id, checkpoint_ns, checkpoint_id)
        blob, content_cid, compression, logical, stored = _pack(checkpoint, metadata)
        now = _now()
        # Idempotent blob upsert (RW PK = implicit upsert; same content_cid is no-op).
        # Pointer row in vertex_langgraph_checkpoint stores blob='' to dedup storage.
        async with _cursor() as cur:
            await cur.execute(
                "INSERT INTO vertex_langgraph_checkpoint_blob "
                "(vertex_id, blob, compression, blob_size_bytes, blob_stored_bytes, "
                "first_seen_at, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (content_cid, blob, compression, logical, stored, now, now),
            )
            await cur.execute(
                "INSERT INTO vertex_langgraph_checkpoint "
                "(vertex_id, thread_id, checkpoint_id, checkpoint_ns, "
                "parent_checkpoint_id, checkpoint_type, blob, "
                "content_cid, compression, blob_size_bytes, blob_stored_bytes, "
                "created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (pk, thread_id, checkpoint_id, checkpoint_ns,
                 parent_checkpoint_id, "json", "",
                 content_cid, compression, logical, 0,
                 now),
            )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, checkpoint_ns, checkpoint_id = _config_to_parts(config)
        if not checkpoint_id:
            return
        now = _now()
        async with _cursor() as cur:
            for idx, (channel, value) in enumerate(writes):
                pk = _write_pk(thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                blob = json.dumps(value, default=str)
                await cur.execute(
                    "INSERT INTO vertex_langgraph_checkpoint_write "
                    "(vertex_id, thread_id, checkpoint_id, checkpoint_ns, "
                    "task_id, task_path, idx, channel, type, blob, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (pk, thread_id, checkpoint_id, checkpoint_ns,
                     task_id, task_path, idx, channel, "json", blob, now),
                )

    # --------------------------------------------------------------- deletion

    async def adelete_thread(self, thread_id: str) -> None:
        async with _cursor() as cur:
            await cur.execute(
                "DELETE FROM vertex_langgraph_checkpoint_write WHERE thread_id = %s",
                (thread_id,),
            )
            await cur.execute(
                "DELETE FROM vertex_langgraph_checkpoint WHERE thread_id = %s",
                (thread_id,),
            )

    # --------------------------------------------------------- version counter

    def get_next_version(self, current: int | None, channel: Any) -> int:
        return (current or 0) + 1

    # ---------------------------------------------------- sync fallback shims

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.aget_tuple(config))

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        import asyncio

        async def _collect() -> list[CheckpointTuple]:
            return [t async for t in self.alist(config, filter=filter, before=before, limit=limit)]

        yield from asyncio.get_event_loop().run_until_complete(_collect())

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.aput(config, checkpoint, metadata, new_versions)
        )

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            self.aput_writes(config, writes, task_id, task_path)
        )


_SAVER_INSTANCE: RisingWaveCheckpointSaver | None = None


async def get_checkpoint_saver() -> RisingWaveCheckpointSaver:
    """Return (or create) the process-level singleton checkpoint saver."""
    global _SAVER_INSTANCE
    if _SAVER_INSTANCE is None:
        _SAVER_INSTANCE = RisingWaveCheckpointSaver()
    return _SAVER_INSTANCE
