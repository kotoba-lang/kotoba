"""
aria.moneyFlowIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_money_flow_ingest` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaMoneyFlowIngestState(TypedDict, total=False):
    ok: bool
    error: str | None


def money_flow_ingest(state: AriaMoneyFlowIngestState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_money_flow_ingest

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_money_flow_ingest(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaMoneyFlowIngestState)
    builder.add_node("money_flow_ingest", money_flow_ingest)
    builder.set_entry_point("money_flow_ingest")
    builder.add_edge("money_flow_ingest", END)
    return builder.compile()
