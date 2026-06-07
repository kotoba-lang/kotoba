"""
osMessaging.crawlOpenChannels — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `os_messaging_crawl_open_channels` (R/PT6H).

Graph:
  START → queue_seed_runs → process_queue → END
"""

from __future__ import annotations

from typing import TypedDict


class OsMessagingCrawlState(TypedDict, total=False):
    queued_count: int
    processed_count: int
    ok: bool
    error: str | None


def queue_seed_runs(state: OsMessagingCrawlState) -> dict:
    from kotodama.primitives.os_messaging_open_channels import task_queue_seed_runs
    try:
        result = task_queue_seed_runs()
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def process_queue(state: OsMessagingCrawlState) -> dict:
    from kotodama.primitives.os_messaging_open_channels import task_process_queue
    try:
        result = task_process_queue()
        return {**(result or {}), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(OsMessagingCrawlState)
    builder.add_node("queue_seed_runs", queue_seed_runs)
    builder.add_node("process_queue", process_queue)
    builder.set_entry_point("queue_seed_runs")
    builder.add_edge("queue_seed_runs", "process_queue")
    builder.add_edge("process_queue", END)
    return builder.compile()
