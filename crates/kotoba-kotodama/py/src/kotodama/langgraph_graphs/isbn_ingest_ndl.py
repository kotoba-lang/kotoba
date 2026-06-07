"""
isbn.ingestNdl — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `isbn_ingest_ndl` (R/PT24H, weekly Mon in practice).
Triggered by K8s CronJob (weekly Monday) via POST /runs.

Graph:
  START → ingest_ndl → END
"""

from __future__ import annotations

from typing import TypedDict


class IsbnIngestNdlState(TypedDict, total=False):
    rows_inserted: int
    ok: bool
    error: str | None


def ingest_ndl(state: IsbnIngestNdlState) -> dict:
    import asyncio
    from kotodama.primitives.isbn import task_isbn_ndl_ingest

    try:
        result = asyncio.run(task_isbn_ndl_ingest())
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(IsbnIngestNdlState)
    builder.add_node("ingest_ndl", ingest_ndl)
    builder.set_entry_point("ingest_ndl")
    builder.add_edge("ingest_ndl", END)
    return builder.compile()
