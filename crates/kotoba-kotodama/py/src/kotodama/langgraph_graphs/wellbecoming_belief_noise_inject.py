"""
wellbecoming.beliefNoiseInject — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_belief_noise_inject` (R/PT1H).
Triggered by K8s CronJob (every hour) via POST /runs.

Graph:
  START → noise_inject → END
"""

from __future__ import annotations

from typing import TypedDict


class WellbecomingBeliefNoiseInjectState(TypedDict, total=False):
    updated_count: int
    ok: bool
    error: str | None


def noise_inject(state: WellbecomingBeliefNoiseInjectState) -> dict:
    from kotodama.primitives.wellbecoming_noise import task_belief_noise_inject

    try:
        result = task_belief_noise_inject()
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingBeliefNoiseInjectState)
    builder.add_node("noise_inject", noise_inject)
    builder.set_entry_point("noise_inject")
    builder.add_edge("noise_inject", END)
    return builder.compile()
