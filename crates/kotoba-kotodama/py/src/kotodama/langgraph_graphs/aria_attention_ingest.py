"""
aria.attentionIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_attention_ingest` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaAttentionIngestState(TypedDict, total=False):
    ok: bool
    error: str | None


def attention_ingest(state: AriaAttentionIngestState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_attention_ingest

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_attention_ingest(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaAttentionIngestState)
    builder.add_node("attention_ingest", attention_ingest)
    builder.set_entry_point("attention_ingest")
    builder.add_edge("attention_ingest", END)
    return builder.compile()
