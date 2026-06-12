"""
wellbecoming.minimaxSweep — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `wellbecoming_minimax_sweep` (R/PT5M).
Triggered by K8s CronJob (every 5 minutes) via POST /runs.

Graph:
  START → minimax_sweep → END
"""

from __future__ import annotations

import asyncio
from typing import TypedDict


class WellbecomingMinimaxSweepState(TypedDict, total=False):
    batch_size: int
    swept_count: int
    ok: bool
    error: str | None


def minimax_sweep(state: WellbecomingMinimaxSweepState) -> dict:
    from kotodama.primitives.wellbecoming_agent import task_wellbecoming_minimax_sweep

    try:
        result = asyncio.run(task_wellbecoming_minimax_sweep(
            batch_size=state.get("batch_size", 3),
        ))
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(WellbecomingMinimaxSweepState)
    builder.add_node("minimax_sweep", minimax_sweep)
    builder.set_entry_point("minimax_sweep")
    builder.add_edge("minimax_sweep", END)
    return builder.compile()
