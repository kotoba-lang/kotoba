"""
aria.minimaxSweep — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_minimax_sweep` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaMinimaxSweepState(TypedDict, total=False):
    ok: bool
    error: str | None


def minimax_sweep(state: AriaMinimaxSweepState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_minimax_sweep

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_minimax_sweep(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaMinimaxSweepState)
    builder.add_node("minimax_sweep", minimax_sweep)
    builder.set_entry_point("minimax_sweep")
    builder.add_edge("minimax_sweep", END)
    return builder.compile()
