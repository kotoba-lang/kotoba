"""
RisingWave-native LangGraph BaseStore (ADR-2605080600).

cross-thread long-term memory store.
namespace = tuple[str, ...] — actor_did を先頭に含める規約:
  ("did:web:shosha.etzhayyim.com", "market_views")
  ("did:web:yoro.etzhayyim.com", "user_prefs", "did:plc:abc123")

Table: vertex_langgraph_store (migration 20260507600000)
  vertex_id  VARCHAR PK  — "{'/'.join(namespace)}:{key}"
  namespace  VARCHAR     — "/".join(namespace)
  key        VARCHAR
  value      VARCHAR     — JSON
  created_at VARCHAR
  updated_at VARCHAR
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

try:
    from langgraph.store.base import (
        BaseStore,
        GetOp,
        Item,
        ListNamespacesOp,
        Op,
        PutOp,
        Result,
        SearchOp,
    )
    _LG_STORE_OK = True
except ImportError:  # pragma: no cover — langgraph is a runtime dep
    _LG_STORE_OK = False
    BaseStore = object  # type: ignore[assignment,misc]
    GetOp = object  # type: ignore[assignment]
    Item = object  # type: ignore[assignment]
    ListNamespacesOp = object  # type: ignore[assignment]
    Op = object  # type: ignore[assignment]
    PutOp = object  # type: ignore[assignment]
    Result = object  # type: ignore[assignment]
    SearchOp = object  # type: ignore[assignment]

LOG = logging.getLogger(__name__)

from kotodama.rw_async_pool import ensure_rw_async_pool as _ensure_pool


def _ns_str(namespace: tuple[str, ...]) -> str:
    return "/".join(namespace)


def _pk(namespace: tuple[str, ...], key: str) -> str:
    return f"{_ns_str(namespace)}:{key}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_item(row: Any) -> Item:
    (_vertex_id, namespace_str, key, value_json, created_at, updated_at) = row
    namespace = tuple(namespace_str.split("/")) if namespace_str else ()
    return Item(
        value=json.loads(value_json) if value_json else {},
        key=key,
        namespace=namespace,
        created_at=datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at,
        updated_at=datetime.fromisoformat(updated_at) if isinstance(updated_at, str) else updated_at,
    )


class RisingWaveStore(BaseStore):
    """LangGraph cross-thread memory store backed by RisingWave vertex_langgraph_store."""

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        results: list[Result] = []
        p = await _ensure_pool()
        async with p.connection() as conn:
            async with conn.cursor() as cur:
                for op in ops:
                    if isinstance(op, GetOp):
                        results.append(await self._get(cur, op))
                    elif isinstance(op, PutOp):
                        await self._put(cur, op)
                        results.append(None)
                    elif isinstance(op, SearchOp):
                        results.append(await self._search(cur, op))
                    elif isinstance(op, ListNamespacesOp):
                        results.append(await self._list_namespaces(cur, op))
                    else:
                        results.append(None)
        return results

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.abatch(ops))

    # ----------------------------------------------------------------- ops

    async def _get(self, cur: Any, op: GetOp) -> Item | None:
        pk = _pk(op.namespace, op.key)
        await cur.execute(
            "SELECT vertex_id, namespace, key, value, created_at, updated_at "
            "FROM vertex_langgraph_store WHERE vertex_id = %s",
            (pk,),
        )
        row = await cur.fetchone()
        return _row_to_item(row) if row else None

    async def _put(self, cur: Any, op: PutOp) -> None:
        pk = _pk(op.namespace, op.key)
        ns = _ns_str(op.namespace)
        now = _now()
        if op.value is None:
            await cur.execute(
                "DELETE FROM vertex_langgraph_store WHERE vertex_id = %s", (pk,)
            )
        else:
            await cur.execute(
                "SELECT created_at FROM vertex_langgraph_store WHERE vertex_id = %s", (pk,)
            )
            existing = await cur.fetchone()
            created_at = existing[0] if existing else now
            value_json = json.dumps(op.value, default=str)
            await cur.execute(
                "INSERT INTO vertex_langgraph_store "
                "(vertex_id, namespace, key, value, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (pk, ns, op.key, value_json, created_at, now),
            )

    async def _search(self, cur: Any, op: SearchOp) -> list[Item]:
        ns_prefix = _ns_str(op.namespace_prefix)
        limit_clause = f"LIMIT {int(op.limit)}" if op.limit else "LIMIT 10"
        offset_clause = f"OFFSET {int(op.offset)}" if op.offset else ""
        filter_clause = ""
        params: list[Any] = [f"{ns_prefix}%"]
        if op.filter:
            for k, v in op.filter.items():
                filter_clause += f" AND value LIKE %s"
                params.append(f'%"{k}": "{v}"%')
        await cur.execute(
            f"SELECT vertex_id, namespace, key, value, created_at, updated_at "
            f"FROM vertex_langgraph_store "
            f"WHERE namespace LIKE %s {filter_clause} "
            f"ORDER BY updated_at DESC {limit_clause} {offset_clause}",
            params,
        )
        rows = await cur.fetchall()
        return [_row_to_item(r) for r in rows]

    async def _list_namespaces(self, cur: Any, op: ListNamespacesOp) -> list[tuple[str, ...]]:
        limit_clause = f"LIMIT {int(op.limit)}" if op.limit else "LIMIT 100"
        offset_clause = f"OFFSET {int(op.offset)}" if op.offset else ""
        await cur.execute(
            f"SELECT DISTINCT namespace FROM vertex_langgraph_store "
            f"ORDER BY namespace {limit_clause} {offset_clause}",
        )
        rows = await cur.fetchall()
        result = []
        for (ns_str,) in rows:
            parts = tuple(ns_str.split("/")) if ns_str else ()
            if op.max_depth is not None:
                parts = parts[: op.max_depth]
            if op.match_conditions:
                if not all(
                    len(parts) > i and parts[i] == cond.match_value
                    for i, cond in enumerate(op.match_conditions)
                ):
                    continue
            result.append(parts)
        return result
