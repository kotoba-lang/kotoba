"""
ki.cycle.v1 — LangGraph StateGraph port of the ki vascular synthesis cycle.

ADR-2605080600 Phase 4: replaces the Zeebe BPMN `ki_vascular_synthesis_cycle`
+ LangServer `ki-zeebe-worker` pool. Triggered by K8s CronJob (R/PT1H) via POST /runs.

Graph (linear with one conditional bloom skip):
  START
    → absorb           (xylem input scan)
    → synthesize       (structured LLM artifact)
    → confidence_gate  (≥ KI_CONFIDENCE_CUTOFF? → bloom else skip)
        ├─ bloom        (phloem publish)
        └─ skip_bloom
    → ring             (growth-ring checkpoint)
    → END

State `KiCycleState` (TypedDict) carries the chain output between nodes
(absorbId, absorbStatus, artifactId, confidence, bloomId, ringId, ok).
"""

from __future__ import annotations

from typing import Any, TypedDict


class KiCycleState(TypedDict, total=False):
    # absorb
    absorbId: str | None
    absorbStatus: str | None
    # synthesize
    artifactId: str | None
    synthesis: str | None
    confidence: float | None
    # bloom
    bloomId: str | None
    publishedAt: str | None
    bloomSkipped: bool
    # ring
    ringId: str | None
    snapshotCount: int | None
    # control
    ok: bool
    error: str | None


async def _absorb_node(state: KiCycleState) -> dict:
    from kotodama.ki_worker_main import task_absorb
    try:
        result = await task_absorb()
        return {
            "absorbId": result.get("absorbId"),
            "absorbStatus": result.get("status") or "absorbed",
            "ok": True,
        }
    except Exception as exc:
        return {"ok": False, "error": f"absorb: {exc}"}


async def _synthesize_node(state: KiCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.ki_worker_main import task_synthesize
    try:
        result = await task_synthesize(absorbId=state.get("absorbId"))
        return {
            "artifactId": result.get("artifactId"),
            "synthesis": result.get("synthesis"),
            "confidence": float(result.get("confidence", 0.0)),
            "ok": True,
        }
    except Exception as exc:
        return {"ok": False, "error": f"synthesize: {exc}"}


async def _bloom_node(state: KiCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.ki_worker_main import task_bloom
    try:
        result = await task_bloom(artifactId=state.get("artifactId"))
        return {
            "bloomId": result.get("bloomId"),
            "publishedAt": result.get("publishedAt"),
            "bloomSkipped": False,
        }
    except Exception as exc:
        return {"ok": False, "error": f"bloom: {exc}"}


def _skip_bloom_node(state: KiCycleState) -> dict:
    return {"bloomSkipped": True, "bloomId": None}


async def _ring_node(state: KiCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.ki_worker_main import task_ring
    try:
        result = await task_ring()
        return {
            "ringId": result.get("ringId"),
            "snapshotCount": int(result.get("snapshotCount", 0)),
        }
    except Exception as exc:
        return {"ok": False, "error": f"ring: {exc}"}


def _confidence_gate(state: KiCycleState) -> str:
    """Conditional edge: bloom only if confidence ≥ cutoff."""
    import os
    cutoff = float(os.environ.get("KI_CONFIDENCE_CUTOFF", "0.6"))
    conf = state.get("confidence") or 0.0
    return "bloom" if conf >= cutoff else "skip_bloom"


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(KiCycleState)
    builder.add_node("absorb", _absorb_node)
    builder.add_node("synthesize", _synthesize_node)
    builder.add_node("bloom", _bloom_node)
    builder.add_node("skip_bloom", _skip_bloom_node)
    builder.add_node("ring", _ring_node)

    builder.set_entry_point("absorb")
    builder.add_edge("absorb", "synthesize")
    builder.add_conditional_edges(
        "synthesize",
        _confidence_gate,
        {"bloom": "bloom", "skip_bloom": "skip_bloom"},
    )
    builder.add_edge("bloom", "ring")
    builder.add_edge("skip_bloom", "ring")
    builder.add_edge("ring", END)

    return builder.compile()
