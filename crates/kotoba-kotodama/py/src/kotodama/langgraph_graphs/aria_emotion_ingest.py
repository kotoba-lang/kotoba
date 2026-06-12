"""
aria.emotionIngest — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `aria_emotion_ingest` (R/PT4H).
"""

from __future__ import annotations

from typing import TypedDict


class AriaEmotionIngestState(TypedDict, total=False):
    ok: bool
    error: str | None


def emotion_ingest(state: AriaEmotionIngestState) -> dict:
    from kotodama.primitives.aria_signal import task_aria_emotion_ingest

    try:
        kwargs = {k: v for k, v in state.items() if k not in ("ok", "error")}
        result = task_aria_emotion_ingest(**kwargs)
        return {**result, "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AriaEmotionIngestState)
    builder.add_node("emotion_ingest", emotion_ingest)
    builder.set_entry_point("emotion_ingest")
    builder.add_edge("emotion_ingest", END)
    return builder.compile()
