"""
adsk.ingestDataset — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `adsk_ingest_dataset` (monthly day 6).
Triggered by K8s CronJob via POST /runs.

Graph:
  START → ingest_all → END
"""

from __future__ import annotations

from typing import TypedDict


class AdskIngestDatasetState(TypedDict, total=False):
    staleSeconds: int
    perDatasetLimit: int
    ok: bool
    error: str | None


def ingest_all(state: AdskIngestDatasetState) -> dict:
    import asyncio
    from kotodama.primitives.adsk import task_adsk_dataset_ingest_all

    try:
        result = asyncio.run(task_adsk_dataset_ingest_all(
            staleSeconds=state.get("staleSeconds", 30 * 24 * 3600),
            perDatasetLimit=state.get("perDatasetLimit", 10000),
        ))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AdskIngestDatasetState)
    builder.add_node("ingest_all", ingest_all)
    builder.set_entry_point("ingest_all")
    builder.add_edge("ingest_all", END)
    return builder.compile()
