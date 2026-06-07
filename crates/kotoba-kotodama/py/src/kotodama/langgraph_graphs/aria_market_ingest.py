"""
aria.marketIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_market_ingest` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaMarketIngestState(TypedDict, total=False):
    ok: bool
    error: str | None


def market_ingest(state: AriaMarketIngestState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_market_delta_ingest

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_market_delta_ingest(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaMarketIngestState)
    builder.add_node("market_ingest", market_ingest)
    builder.set_entry_point("market_ingest")
    builder.add_edge("market_ingest", END)
    return builder.compile()
