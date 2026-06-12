"""
wellbecoming.floorViolationAlert — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_floor_violation_alert` (R/PT30M).
Triggered by K8s CronJob (every 30 minutes) via POST /runs.

Graph:
  START → floor_check → (has_violations?) → floor_alert → END
                      ↘ (no violations)               → END
"""

from __future__ import annotations

from typing import Any
from typing import TypedDict


class WellbecomingFloorViolationAlertState(TypedDict, total=False):
    window_minutes: int
    floor_violation_count: int
    violation_ids: list[Any]
    has_violations: bool
    alert_emitted: bool
    ok: bool
    error: str | None


def floor_check(state: WellbecomingFloorViolationAlertState) -> dict:
    from kotodama.primitives.wellbecoming_agent import task_wellbecoming_floor_check

    try:
        result = task_wellbecoming_floor_check(
            window_minutes=state.get("window_minutes", 30),
        )
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e), "has_violations": False}


def floor_alert(state: WellbecomingFloorViolationAlertState) -> dict:
    from kotodama.primitives.wellbecoming_agent import task_wellbecoming_floor_alert

    try:
        result = task_wellbecoming_floor_alert(
            floor_violation_count=state.get("floor_violation_count", 0),
            violation_ids=state.get("violation_ids"),
        )
        return {**result, "alert_emitted": True, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e), "alert_emitted": False}


def _route_after_check(state: WellbecomingFloorViolationAlertState) -> str:
    if state.get("has_violations") and not state.get("error"):
        return "floor_alert"
    return "__end__"


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingFloorViolationAlertState)
    builder.add_node("floor_check", floor_check)
    builder.add_node("floor_alert", floor_alert)
    builder.set_entry_point("floor_check")
    builder.add_conditional_edges("floor_check", _route_after_check, {
        "floor_alert": "floor_alert",
        "__end__": END,
    })
    builder.add_edge("floor_alert", END)
    return builder.compile()
