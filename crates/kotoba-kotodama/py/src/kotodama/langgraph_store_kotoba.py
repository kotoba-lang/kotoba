"""
kotoba-native LangGraph BaseStore (ADR-2605262130 + ADR-2605312345).

RW-free replacement for ``langgraph_store_rw.RisingWaveStore`` — cross-thread
long-term memory in the kotoba Datom log via ``KotobaDatomicClient``.

namespace = tuple[str, ...], actor_did-prefixed by convention:
  ("did:web:shosha.etzhayyim.com", "market_views")

Legacy table ``vertex_langgraph_store`` → ``:lg.store/*`` entities keyed by
``:lg.store/vertex-id`` = ``"{'/'.join(namespace)}:{key}"`` (:db.unique/identity,
so a re-put upserts). Search/list filtering runs in Python over the pulled set
(R0 memory-store scale); no datalog ordering relied upon.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterable

from kotodama.kotoba_datomic import KotobaDatomicClient, edn_str, get_kotoba_client, to_tx_edn

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
except (ImportError, SystemError):  # pragma: no cover — langgraph runtime dep / broken transitive dep
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

STORE_GRAPH = os.environ.get("KOTODAMA_KOTOBA_LG_GRAPH", "etzhayyim/kotoba-kotodama/langgraph")
NS_STORE = "lg.store"


# ─────────────────────────── pure helpers (langgraph-free, testable) ───────────────────────────

def _ns_str(namespace: tuple[str, ...]) -> str:
    return "/".join(namespace)


def _pk(namespace: tuple[str, ...], key: str) -> str:
    return f"{_ns_str(namespace)}:{key}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_entity(pk: str, ns: str, key: str, value_json: str, created_at: str, now: str) -> dict[str, Any]:
    return {
        f":{NS_STORE}/vertex-id": pk,
        f":{NS_STORE}/namespace": ns,
        f":{NS_STORE}/key": key,
        f":{NS_STORE}/value": value_json,
        f":{NS_STORE}/created-at": created_at,
        f":{NS_STORE}/updated-at": now,
    }


def _strip(ent: Any) -> dict[str, Any]:
    prefix = f":{NS_STORE}/"
    out: dict[str, Any] = {}
    if not isinstance(ent, dict):
        return out
    for k, v in ent.items():
        key = str(k)
        col = key[len(prefix):] if key.startswith(prefix) else key.lstrip(":")
        out[col.replace("-", "_")] = v
    return out


def _record_to_item(rec: dict[str, Any]) -> Any:
    ns_str = rec.get("namespace", "")
    namespace = tuple(ns_str.split("/")) if ns_str else ()
    created_at = rec.get("created_at")
    updated_at = rec.get("updated_at")
    return Item(
        value=json.loads(rec["value"]) if rec.get("value") else {},
        key=rec.get("key", ""),
        namespace=namespace,
        created_at=datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at,
        updated_at=datetime.fromisoformat(updated_at) if isinstance(updated_at, str) else updated_at,
    )


# ─────────────────────────── store ───────────────────────────

class KotobaStore(BaseStore):
    """LangGraph cross-thread memory store backed by the kotoba Datom log."""

    def __init__(self, client: KotobaDatomicClient | None = None) -> None:
        self._client = client or get_kotoba_client()
        self._graph = STORE_GRAPH

    async def _all_records(self) -> list[dict[str, Any]]:
        q = f"[:find (pull ?e [*]) :where [?e :{NS_STORE}/vertex-id _]]"
        rows = await asyncio.to_thread(self._client.q, q, graph=self._graph)
        recs = []
        for it in rows:
            recs.append(_strip(it[0] if isinstance(it, (list, tuple)) and it else it))
        return [r for r in recs if r.get("vertex_id")]

    async def _get_record(self, pk: str) -> dict[str, Any] | None:
        q = f"[:find (pull ?e [*]) :where [?e :{NS_STORE}/vertex-id {edn_str(pk)}]]"
        rows = await asyncio.to_thread(self._client.q, q, graph=self._graph)
        for it in rows:
            rec = _strip(it[0] if isinstance(it, (list, tuple)) and it else it)
            if rec.get("vertex_id"):
                return rec
        return None

    async def abatch(self, ops: Iterable[Any]) -> list[Any]:
        results: list[Any] = []
        for op in ops:
            if isinstance(op, GetOp):
                results.append(await self._get(op))
            elif isinstance(op, PutOp):
                await self._put(op)
                results.append(None)
            elif isinstance(op, SearchOp):
                results.append(await self._search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(await self._list_namespaces(op))
            else:
                results.append(None)
        return results

    def batch(self, ops: Iterable[Any]) -> list[Any]:
        return asyncio.get_event_loop().run_until_complete(self.abatch(ops))

    # ----------------------------------------------------------------- ops
    async def _get(self, op: Any) -> Any:
        rec = await self._get_record(_pk(op.namespace, op.key))
        return _record_to_item(rec) if rec else None

    async def _put(self, op: Any) -> None:
        pk = _pk(op.namespace, op.key)
        now = _now()
        if op.value is None:
            await asyncio.to_thread(
                self._client.transact,
                to_tx_edn([{f":{NS_STORE}/vertex-id": pk, ":db/retractEntity": True}], [f"store retract {pk}"]),
                graph=self._graph,
            )
            return
        existing = await self._get_record(pk)
        created_at = existing.get("created_at") if existing else now
        ent = _store_entity(pk, _ns_str(op.namespace), op.key, json.dumps(op.value, default=str), created_at, now)
        await asyncio.to_thread(self._client.transact, to_tx_edn([ent], [f"store put {pk}"]), graph=self._graph)

    async def _search(self, op: Any) -> list[Any]:
        ns_prefix = _ns_str(op.namespace_prefix)
        recs = await self._all_records()
        recs = [r for r in recs if str(r.get("namespace", "")).startswith(ns_prefix)]
        if getattr(op, "filter", None):
            def _match(rec: dict[str, Any]) -> bool:
                try:
                    val = json.loads(rec.get("value") or "{}")
                except json.JSONDecodeError:
                    return False
                return all(val.get(k) == v for k, v in op.filter.items())
            recs = [r for r in recs if _match(r)]
        recs.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        offset = int(getattr(op, "offset", 0) or 0)
        limit = int(getattr(op, "limit", 10) or 10)
        return [_record_to_item(r) for r in recs[offset: offset + limit]]

    async def _list_namespaces(self, op: Any) -> list[tuple[str, ...]]:
        recs = await self._all_records()
        seen: dict[str, None] = {}
        for r in recs:
            seen.setdefault(str(r.get("namespace", "")), None)
        result: list[tuple[str, ...]] = []
        for ns_str in sorted(seen):
            parts = tuple(ns_str.split("/")) if ns_str else ()
            if getattr(op, "max_depth", None) is not None:
                parts = parts[: op.max_depth]
            if getattr(op, "match_conditions", None):
                if not all(
                    len(parts) > i and parts[i] == cond.match_value
                    for i, cond in enumerate(op.match_conditions)
                ):
                    continue
            result.append(parts)
        offset = int(getattr(op, "offset", 0) or 0)
        limit = int(getattr(op, "limit", 100) or 100)
        return result[offset: offset + limit]


_STORE_INSTANCE: KotobaStore | None = None


def get_store() -> KotobaStore:
    """Return (or create) the process-level singleton kotoba store."""
    global _STORE_INSTANCE
    if _STORE_INSTANCE is None:
        _STORE_INSTANCE = KotobaStore()
    return _STORE_INSTANCE
