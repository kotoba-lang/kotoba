"""biblio.openDataIngest - global bibliographic open-data ingest graph."""

from __future__ import annotations

from typing import Any, TypedDict


class BiblioOpenDataIngestState(TypedDict, total=False):
    sourceIds: list[str]
    mode: str
    rawRecords: list[dict[str, Any]]
    ok: bool
    error: str


def _run(state: BiblioOpenDataIngestState) -> dict[str, Any]:
    from kotodama.primitives.biblio_open_data import task_biblio_open_data_ingest

    return task_biblio_open_data_ingest(
        sourceIds=state.get("sourceIds"),
        rawRecords=state.get("rawRecords"),
        mode=str(state.get("mode") or "source_catalog"),
    )


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(BiblioOpenDataIngestState)
    builder.add_node("ingest", _run)
    builder.set_entry_point("ingest")
    builder.add_edge("ingest", END)
    return builder.compile()
