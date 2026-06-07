"""
wellbecoming.proactiveConnect — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_proactive_connect` (R/PT2H).
Triggered by K8s CronJob (every 2 hours) via POST /runs.

Graph:
  START → proactive_connect → END
"""

from __future__ import annotations

from typing import TypedDict


class WellbecomingProactiveConnectState(TypedDict, total=False):
    batch_size: int
    connected_count: int
    ok: bool
    error: str | None


def proactive_connect(state: WellbecomingProactiveConnectState) -> dict:
    from kotodama.primitives.wellbecoming_agent import task_wellbecoming_proactive_connect

    try:
        result = task_wellbecoming_proactive_connect(
            batch_size=state.get("batch_size", 10),
        )
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingProactiveConnectState)
    builder.add_node("proactive_connect", proactive_connect)
    builder.set_entry_point("proactive_connect")
    builder.add_edge("proactive_connect", END)
    return builder.compile()
