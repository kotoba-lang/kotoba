"""
isbn.ingestOpenLibrary — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `isbn_ingest_open_library` (monthly day 5).
Triggered by K8s CronJob (monthly) via POST /runs.

Graph:
  START → ingest_open_library → END
"""

from __future__ import annotations

from typing import TypedDict


class IsbnIngestOpenLibraryState(TypedDict, total=False):
    limit: int | None
    rows_inserted: int
    ok: bool
    error: str | None


def ingest_open_library(state: IsbnIngestOpenLibraryState) -> dict:
    import asyncio
    from kotodama.primitives.isbn import task_isbn_open_library_ingest

    try:
        result = asyncio.run(task_isbn_open_library_ingest(
            limit=state.get("limit"),
        ))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(IsbnIngestOpenLibraryState)
    builder.add_node("ingest_open_library", ingest_open_library)
    builder.set_entry_point("ingest_open_library")
    builder.add_edge("ingest_open_library", END)
    return builder.compile()
