"""patent.blobConvert — LangGraph Functional API port (ADR-2605080600 Phase 5+).

Replaces Zeebe timer-start BPMN `patent_blob_convert` (every 5 min).
Self-selects pending patent_blob entities from the kotoba Datom log then converts (PDF → webp + OCR).

Migrated from StateGraph → Functional API (P2, 2026-05-09):
  - Single linear pipeline, no branching → @entrypoint + @task wins
  - Removed StateGraph machinery (state schema, add_node, add_edge, set_entry_point)
  - `build_graph()` retained as loader-compatibility shim returning the
    @entrypoint object (which exposes `.invoke()` / `.ainvoke()` /
    `.astream_events()` like a compiled StateGraph).

Topology (logical):
  fetch_pending → convert_blobs

State (input dict / output dict):
  in:  { limit?: int }              — default 25
  out: { converted: int, ok: bool, error?: str, ... }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict

from kotodama.kotoba_datomic import get_kotoba_client


class PatentBlobConvertState(TypedDict, total=False):
    limit: int
    converted: int
    ok: bool
    error: str | None


def _select_pending(limit: int) -> list[dict[str, Any]]:
    # R0: Replaced SQLAlchemy select with Datalog query due to complex predicates,
    # ordering, and limiting which are best handled by a raw Datalog query.
    query_edn = """
    [:find ?vertex_id ?patent_number ?jurisdiction ?pdf_source_url
     :where
       [?e :vertex_patent_blob/status "pending"]
       [?e :vertex_patent_blob/pdf_source_url ?pdf_source_url]
       (not (= ?pdf_source_url nil))
       [?e :vertex_patent_blob/vertex_id ?vertex_id]
       [?e :vertex_patent_blob/patent_number ?patent_number]
       [?e :vertex_patent_blob/jurisdiction ?jurisdiction]
       [?e :vertex_patent_blob/collected_at ?collected_at]
     :order-by ?collected_at
     :limit ?limit]
    """
    rows = get_kotoba_client().q(query_edn, args={"?limit": limit})
    # The Datalog query returns a list of lists. Convert to list of dicts.
    # The order of fields in :find must match the keys here.
    return [
        {
            "vertex_id": row[0],
            "patent_number": row[1],
            "jurisdiction": row[2],
            "pdf_source_url": row[3],
        }
        for row in rows
    ] or []


async def _convert(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from kotodama.primitives.patent import task_patent_blob_convert

    return await task_patent_blob_convert(rows=rows)


def build_graph():
    """Return the compiled entrypoint. Loader-compatibility shim.

    Wraps the functional pipeline in a LangGraph @entrypoint so callers
    that expect a compiled-graph interface (`.invoke()` / `.ainvoke()` /
    `.astream_events()`) continue to work unchanged.
    """
    from langgraph.func import entrypoint, task

    @task  # type: ignore[misc]
    def fetch_pending(limit: int) -> list[dict[str, Any]]:
        return _select_pending(limit)

    @task  # type: ignore[misc]
    async def convert_blobs(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return await _convert(rows)

    @entrypoint()  # type: ignore[misc]
    async def patent_blob_convert(state: PatentBlobConvertState) -> dict[str, Any]:
        try:
            limit = int(state.get("limit", 25)) if isinstance(state, dict) else 25
            rows = await fetch_pending(limit)
            if not rows:
                return {"converted": 0, "ok": True}
            result = await convert_blobs(rows)
            return {**result, "converted": result.get("ok_count", len(rows)), "ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "converted": 0}

    return patent_blob_convert
