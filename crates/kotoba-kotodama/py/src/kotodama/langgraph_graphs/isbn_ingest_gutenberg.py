"""
isbn.ingestGutenberg — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `isbn_ingest_gutenberg` (R/PT24H).
Triggered by K8s CronJob (daily) via POST /runs.

Graph:
  START → ingest_gutenberg → END
"""

from __future__ import annotations

from typing import TypedDict


class IsbnIngestGutenbergState(TypedDict, total=False):
    fulltext: bool
    limit: int | None
    rows_inserted: int
    ok: bool
    error: str | None


def ingest_gutenberg(state: IsbnIngestGutenbergState) -> dict:
    import asyncio
    from kotodama.primitives.isbn import task_isbn_gutenberg_ingest

    try:
        result = asyncio.run(task_isbn_gutenberg_ingest(
            fulltext=state.get("fulltext", True),
            limit=state.get("limit"),
        ))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(IsbnIngestGutenbergState)
    builder.add_node("ingest_gutenberg", ingest_gutenberg)
    builder.set_entry_point("ingest_gutenberg")
    builder.add_edge("ingest_gutenberg", END)
    return builder.compile()
