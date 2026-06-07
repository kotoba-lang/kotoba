"""
isbn.ingestHathitrust — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `isbn_ingest_hathitrust` (monthly day 8).
Triggered by K8s CronJob (monthly) via POST /runs.

Graph:
  START → ingest_hathitrust → END
"""

from __future__ import annotations

from typing import TypedDict


class IsbnIngestHathitrustState(TypedDict, total=False):
    limit: int | None
    rows_inserted: int
    ok: bool
    error: str | None


def ingest_hathitrust(state: IsbnIngestHathitrustState) -> dict:
    import asyncio
    from kotodama.primitives.isbn import task_isbn_hathitrust_ingest

    try:
        result = asyncio.run(task_isbn_hathitrust_ingest(
            limit=state.get("limit"),
        ))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(IsbnIngestHathitrustState)
    builder.add_node("ingest_hathitrust", ingest_hathitrust)
    builder.set_entry_point("ingest_hathitrust")
    builder.add_edge("ingest_hathitrust", END)
    return builder.compile()
