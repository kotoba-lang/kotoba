"""
patent.ingestUsptoWeekly — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `patent_ingest_uspto_weekly` (Sunday midnight).

Graph:
  START → ingest_patent → ingest_citation → ingest_epo_citations → END
"""

from __future__ import annotations

from typing import TypedDict


class PatentIngestUsptoWeeklyState(TypedDict, total=False):
    maxRows: int | None
    epoBatchSize: int | None
    patent_result: dict
    citation_result: dict
    epo_result: dict
    ok: bool
    error: str | None


def ingest_patent(state: PatentIngestUsptoWeeklyState) -> dict:
    from kotodama.primitives.patent_ingest import task_patent_uspto_patentsview_ingest_patent

    try:
        result = task_patent_uspto_patentsview_ingest_patent(maxRows=state.get("maxRows"))
        return {"patent_result": result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e), "patent_result": {}}


def ingest_citation(state: PatentIngestUsptoWeeklyState) -> dict:
    from kotodama.primitives.patent_ingest import task_patent_uspto_patentsview_ingest_citation

    try:
        result = task_patent_uspto_patentsview_ingest_citation(maxRows=state.get("maxRows"))
        return {"citation_result": result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e), "citation_result": {}}


def ingest_epo_citations(state: PatentIngestUsptoWeeklyState) -> dict:
    from kotodama.primitives.patent_ingest import task_patent_epo_ops_fill_citations

    batch_size = state.get("epoBatchSize") or 100
    try:
        result = task_patent_epo_ops_fill_citations(batchSize=batch_size)
        return {"epo_result": result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e), "epo_result": {}}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(PatentIngestUsptoWeeklyState)
    builder.add_node("ingest_patent", ingest_patent)
    builder.add_node("ingest_citation", ingest_citation)
    builder.add_node("ingest_epo_citations", ingest_epo_citations)
    builder.set_entry_point("ingest_patent")
    builder.add_edge("ingest_patent", "ingest_citation")
    builder.add_edge("ingest_citation", "ingest_epo_citations")
    builder.add_edge("ingest_epo_citations", END)
    return builder.compile()
