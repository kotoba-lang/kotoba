"""
wellbecoming.trustWeightUpdate — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_trust_weight_update` (R/PT1H).
Triggered by K8s CronJob (every hour) via POST /runs.

Graph:
  START → trust_weight_update → END
"""

from __future__ import annotations

from typing import TypedDict


class WellbecomingTrustWeightUpdateState(TypedDict, total=False):
    updated_count: int
    ok: bool
    error: str | None


def trust_weight_update(state: WellbecomingTrustWeightUpdateState) -> dict:
    from kotodama.primitives.wellbecoming_trust import task_trust_weight_update

    try:
        result = task_trust_weight_update()
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingTrustWeightUpdateState)
    builder.add_node("trust_weight_update", trust_weight_update)
    builder.set_entry_point("trust_weight_update")
    builder.add_edge("trust_weight_update", END)
    return builder.compile()
