"""
wellbecoming.processMining — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_process_mining` (R/PT6H).
Triggered by K8s CronJob (every 6 hours) via POST /runs.

Graph:
  START → process_mining → END
"""

from __future__ import annotations

from typing import Any
from typing import TypedDict


class WellbecomingProcessMiningState(TypedDict, total=False):
    batch_size: int | None
    scored_count: int
    floor_violations: int
    avg_spirit: float | None
    avg_separation_delta: float | None
    report_uri: str
    ok: bool
    error: str | None


def process_mining(state: WellbecomingProcessMiningState) -> dict:
    from kotodama.primitives.wellbecoming_process_mining import analyze

    try:
        result = analyze(batch_size=state.get("batch_size"))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingProcessMiningState)
    builder.add_node("process_mining", process_mining)
    builder.set_entry_point("process_mining")
    builder.add_edge("process_mining", END)
    return builder.compile()
