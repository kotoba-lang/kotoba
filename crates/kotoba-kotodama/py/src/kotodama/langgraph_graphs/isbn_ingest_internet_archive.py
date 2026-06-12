"""
isbn.ingestInternetArchive — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `isbn_ingest_internet_archive` (monthly).
Triggered by K8s CronJob (monthly day 12) via POST /runs.

Graph:
  START → ingest_internet_archive → END
"""

from __future__ import annotations

from typing import TypedDict


class IsbnIngestInternetArchiveState(TypedDict, total=False):
    fulltext: bool
    limit: int | None
    rows_inserted: int
    ok: bool
    error: str | None


def ingest_internet_archive(state: IsbnIngestInternetArchiveState) -> dict:
    import asyncio
    from kotodama.primitives.isbn import task_isbn_internet_archive_ingest

    try:
        result = asyncio.run(task_isbn_internet_archive_ingest(
            fulltext=state.get("fulltext", True),
            limit=state.get("limit"),
        ))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(IsbnIngestInternetArchiveState)
    builder.add_node("ingest_internet_archive", ingest_internet_archive)
    builder.set_entry_point("ingest_internet_archive")
    builder.add_edge("ingest_internet_archive", END)
    return builder.compile()
