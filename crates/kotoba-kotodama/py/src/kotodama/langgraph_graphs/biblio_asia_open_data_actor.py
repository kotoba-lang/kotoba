"""biblio.asiaOpenDataActor - India/China/Korea bibliographic ingest actor.

Input:
  {
    countries?: ["india", "china", "korea"],
    sourceIds?: ["ind-nli-opac", "chn-nlc", "kor-nlk-openapi"],
    rawRecordsBySource?: {"kor-nlk-openapi": [{...}]},
    maxRecordsPerSource?: 200,
    fetchEntrypoints?: true,
    ocr?: false,
    maxOcrPagesPerSource?: 2,
    webpQuality?: 82,
    dryRun?: false
  }
"""

from __future__ import annotations

from typing import Any, TypedDict


class BiblioAsiaOpenDataState(TypedDict, total=False):
    countries: list[str]
    sourceIds: list[str]
    rawRecordsBySource: dict[str, list[dict[str, Any]]]
    maxRecordsPerSource: int
    fetchEntrypoints: bool
    ocr: bool
    maxOcrPagesPerSource: int
    webpQuality: int
    dryRun: bool
    ok: bool
    error: str


def _ingest(state: BiblioAsiaOpenDataState) -> dict[str, Any]:
    from kotodama.primitives.biblio_open_data import task_biblio_asia_open_data_actor

    return task_biblio_asia_open_data_actor(
        countries=state.get("countries"),
        sourceIds=state.get("sourceIds"),
        rawRecordsBySource=state.get("rawRecordsBySource"),
        maxRecordsPerSource=int(state.get("maxRecordsPerSource") or 200),
        fetchEntrypoints=bool(state.get("fetchEntrypoints", True)),
        ocr=bool(state.get("ocr", False)),
        maxOcrPagesPerSource=int(state.get("maxOcrPagesPerSource") or 2),
        webpQuality=int(state.get("webpQuality") or 82),
        dryRun=bool(state.get("dryRun", False)),
    )


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(BiblioAsiaOpenDataState)
    builder.add_node("ingest", _ingest)
    builder.set_entry_point("ingest")
    builder.add_edge("ingest", END)
    return builder.compile()
