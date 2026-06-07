"""
aria.influenceIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_influence_ingest` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaInfluenceIngestState(TypedDict, total=False):
    ok: bool
    error: str | None


def influence_ingest(state: AriaInfluenceIngestState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_influence_ingest

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_influence_ingest(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaInfluenceIngestState)
    builder.add_node("influence_ingest", influence_ingest)
    builder.set_entry_point("influence_ingest")
    builder.add_edge("influence_ingest", END)
    return builder.compile()
