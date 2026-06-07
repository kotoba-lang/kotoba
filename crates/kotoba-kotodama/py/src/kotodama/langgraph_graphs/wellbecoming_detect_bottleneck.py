"""
wellbecoming.detectBottleneck — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_detect_bottleneck` (R/PT1H).
Triggered by K8s CronJob (every hour) via POST /runs.

Graph:
  START → detect_bottleneck → END
"""

from __future__ import annotations

from typing import TypedDict


class WellbecomingDetectBottleneckState(TypedDict, total=False):
    batch_size: int
    bottleneck_count: int
    updated_count: int
    ok: bool
    error: str | None


def detect_bottleneck(state: WellbecomingDetectBottleneckState) -> dict:
    from kotodama.primitives.wellbecoming_agent import task_wellbecoming_bottleneck_detect

    try:
        result = task_wellbecoming_bottleneck_detect(
            batch_size=state.get("batch_size", 100),
        )
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingDetectBottleneckState)
    builder.add_node("detect_bottleneck", detect_bottleneck)
    builder.set_entry_point("detect_bottleneck")
    builder.add_edge("detect_bottleneck", END)
    return builder.compile()
