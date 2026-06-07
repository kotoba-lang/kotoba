"""
onion.crawlSeeds — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `onion_crawl_seeds` (R/PT6H).

Graph:
  START → queue_seeds → process_queue → END
"""

from __future__ import annotations

from typing import TypedDict


class OnionCrawlSeedsState(TypedDict, total=False):
    queued_count: int
    processed_count: int
    ok: bool
    error: str | None


def queue_seeds(state: OnionCrawlSeedsState) -> dict:
    from kotodama.primitives.onion_crawl import task_queue_seeds
    try:
        result = task_queue_seeds()
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def process_queue(state: OnionCrawlSeedsState) -> dict:
    from kotodama.primitives.onion_crawl import task_process_queue
    try:
        result = task_process_queue()
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(OnionCrawlSeedsState)
    builder.add_node("queue_seeds", queue_seeds)
    builder.add_node("process_queue", process_queue)
    builder.set_entry_point("queue_seeds")
    builder.add_edge("queue_seeds", "process_queue")
    builder.add_edge("process_queue", END)
    return builder.compile()
