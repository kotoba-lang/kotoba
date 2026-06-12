"""
coverage.gapBridge — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces Zeebe timer-start BPMN `coverage_gap_bridge` (R/PT6H, 5-task chain).

Graph:
  START → stats_sync → scan → ingest → infer → generate → END

Each node delegates to a sync primitive in kotodama.primitives.coverage_gap.
"""

from __future__ import annotations

from typing import TypedDict


class CoverageGapBridgeState(TypedDict, total=False):
    domain: str
    worldTotal: int
    llmTier: str
    ok: bool
    error: str | None
    stats_result: dict
    scan_result: dict
    ingest_result: dict
    infer_result: dict
    generate_result: dict


def _safe(fn, **kwargs):
    try:
        return {"ok": True, "result": fn(**kwargs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def stats_sync_node(state: CoverageGapBridgeState) -> dict:
    from kotodama.primitives.coverage_gap import task_coverage_gap_stats_sync
    out = _safe(task_coverage_gap_stats_sync)
    return {"stats_result": out.get("result", {}), "ok": out["ok"], "error": out.get("error")}


def scan_node(state: CoverageGapBridgeState) -> dict:
    from kotodama.primitives.coverage_gap import task_coverage_gap_scan
    out = _safe(task_coverage_gap_scan)
    return {"scan_result": out.get("result", {}), "ok": out["ok"], "error": out.get("error")}


def ingest_node(state: CoverageGapBridgeState) -> dict:
    from kotodama.primitives.coverage_gap import task_coverage_gap_ingest
    out = _safe(
        task_coverage_gap_ingest,
        domain=state.get("domain", ""),
        worldTotal=state.get("worldTotal", 0),
    )
    return {"ingest_result": out.get("result", {}), "ok": out["ok"], "error": out.get("error")}


def infer_node(state: CoverageGapBridgeState) -> dict:
    from kotodama.primitives.coverage_gap import task_coverage_gap_infer
    out = _safe(
        task_coverage_gap_infer,
        domain=state.get("domain", ""),
        llmTier=state.get("llmTier", "structured"),
    )
    return {"infer_result": out.get("result", {}), "ok": out["ok"], "error": out.get("error")}


def generate_node(state: CoverageGapBridgeState) -> dict:
    from kotodama.primitives.coverage_gap import task_coverage_gap_generate
    out = _safe(task_coverage_gap_generate)
    return {"generate_result": out.get("result", {}), "ok": out["ok"], "error": out.get("error")}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(CoverageGapBridgeState)
    builder.add_node("stats_sync", stats_sync_node)
    builder.add_node("scan", scan_node)
    builder.add_node("ingest", ingest_node)
    builder.add_node("infer", infer_node)
    builder.add_node("generate", generate_node)
    builder.set_entry_point("stats_sync")
    builder.add_edge("stats_sync", "scan")
    builder.add_edge("scan", "ingest")
    builder.add_edge("ingest", "infer")
    builder.add_edge("infer", "generate")
    builder.add_edge("generate", END)
    return builder.compile()
