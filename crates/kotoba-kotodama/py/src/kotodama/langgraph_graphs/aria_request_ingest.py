"""
aria.requestIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_request_ingest` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaRequestIngestState(TypedDict, total=False):
    ok: bool
    error: str | None


def request_ingest(state: AriaRequestIngestState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_request_ingest

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_request_ingest(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaRequestIngestState)
    builder.add_node("request_ingest", request_ingest)
    builder.set_entry_point("request_ingest")
    builder.add_edge("request_ingest", END)
    return builder.compile()
