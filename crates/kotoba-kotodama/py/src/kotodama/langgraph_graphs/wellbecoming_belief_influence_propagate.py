"""
wellbecoming.beliefInfluencePropagate — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_belief_influence_propagate` (R/PT1H).
Triggered by K8s CronJob (every hour) via POST /runs.

Graph:
  START → influence_propagate → END
"""

from __future__ import annotations

from typing import TypedDict


class WellbecomingBeliefInfluencePropagateState(TypedDict, total=False):
    updated_count: int
    ok: bool
    error: str | None


def influence_propagate(state: WellbecomingBeliefInfluencePropagateState) -> dict:
    from kotodama.primitives.wellbecoming_influence import task_belief_influence_propagate

    try:
        result = task_belief_influence_propagate()
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingBeliefInfluencePropagateState)
    builder.add_node("influence_propagate", influence_propagate)
    builder.set_entry_point("influence_propagate")
    builder.add_edge("influence_propagate", END)
    return builder.compile()
