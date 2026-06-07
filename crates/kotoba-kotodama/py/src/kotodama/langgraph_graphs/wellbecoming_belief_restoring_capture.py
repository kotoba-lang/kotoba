"""
wellbecoming.beliefRestoringCapture — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_belief_restoring_capture` (R/PT1H).
Triggered by K8s CronJob (every hour) via POST /runs.

Graph:
  START → restoring_capture → END
"""

from __future__ import annotations

from typing import TypedDict


class WellbecomingBeliefRestoringCaptureState(TypedDict, total=False):
    updated_count: int
    ok: bool
    error: str | None


def restoring_capture(state: WellbecomingBeliefRestoringCaptureState) -> dict:
    from kotodama.primitives.wellbecoming_restoring import task_belief_restoring_capture

    try:
        result = task_belief_restoring_capture()
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingBeliefRestoringCaptureState)
    builder.add_node("restoring_capture", restoring_capture)
    builder.set_entry_point("restoring_capture")
    builder.add_edge("restoring_capture", END)
    return builder.compile()
