"""
koke.cycle.v1 — LangGraph StateGraph port of koke photosynthesis cycle.

ADR-2605080600 Phase 4: replaces the Zeebe BPMN `koke_photosynthesis_cycle`.

Graph (scan → optional fix → classify → branch by confidence):
  START
    → scan
    → has_signals_gate
        ├─ no → END
        └─ yes → fix
                  → classify
                    → confidence_gate
                        ├─ high (≥0.7) → handoff_to_hakkou → END
                        └─ low  (<0.7) → handoff_to_saikin → END
"""

from __future__ import annotations

from typing import Any, TypedDict


class KokeCycleState(TypedDict, total=False):
    signalCount: int
    signals: list[Any]
    fixationId: str | None
    classifyKind: str | None
    confidence: float
    hakkouHandoffId: str | None
    saikinHandoffId: str | None
    ok: bool
    error: str | None


async def _scan_node(state: KokeCycleState) -> dict:
    from kotodama.koke_worker_main import task_scan_raw_signals
    try:
        r = await task_scan_raw_signals()
        return {
            "signalCount": int(r.get("signalCount", 0)),
            "signals": r.get("signals") or [],
            "ok": True,
        }
    except Exception as exc:
        return {"ok": False, "error": f"scan: {exc}"}


async def _fix_node(state: KokeCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.koke_worker_main import task_fix_signal
    try:
        r = await task_fix_signal(signals=state.get("signals") or [])
        return {"fixationId": r.get("fixationId")}
    except Exception as exc:
        return {"ok": False, "error": f"fix: {exc}"}


async def _classify_node(state: KokeCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.koke_worker_main import task_classify_fixation
    try:
        r = await task_classify_fixation(fixationId=state.get("fixationId"))
        return {
            "classifyKind": r.get("kind"),
            "confidence": float(r.get("confidence", 0.0)),
        }
    except Exception as exc:
        return {"ok": False, "error": f"classify: {exc}"}


async def _handoff_hakkou_node(state: KokeCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.koke_worker_main import task_handoff_to_hakkou
    try:
        r = await task_handoff_to_hakkou(fixationId=state.get("fixationId"))
        return {"hakkouHandoffId": r.get("handoffId")}
    except Exception as exc:
        return {"ok": False, "error": f"handoff_hakkou: {exc}"}


async def _handoff_saikin_node(state: KokeCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.koke_worker_main import task_handoff_to_saikin
    try:
        r = await task_handoff_to_saikin(fixationId=state.get("fixationId"))
        return {"saikinHandoffId": r.get("handoffId")}
    except Exception as exc:
        return {"ok": False, "error": f"handoff_saikin: {exc}"}


def _has_signals_gate(state: KokeCycleState) -> str:
    return "fix" if int(state.get("signalCount", 0) or 0) > 0 else "no_signals"


def _confidence_gate(state: KokeCycleState) -> str:
    return "hakkou" if (state.get("confidence") or 0.0) >= 0.7 else "saikin"


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(KokeCycleState)
    builder.add_node("scan", _scan_node)
    builder.add_node("fix", _fix_node)
    builder.add_node("classify", _classify_node)
    builder.add_node("handoff_hakkou", _handoff_hakkou_node)
    builder.add_node("handoff_saikin", _handoff_saikin_node)

    builder.set_entry_point("scan")
    builder.add_conditional_edges(
        "scan",
        _has_signals_gate,
        {"fix": "fix", "no_signals": END},
    )
    builder.add_edge("fix", "classify")
    builder.add_conditional_edges(
        "classify",
        _confidence_gate,
        {"hakkou": "handoff_hakkou", "saikin": "handoff_saikin"},
    )
    builder.add_edge("handoff_hakkou", END)
    builder.add_edge("handoff_saikin", END)

    return builder.compile()
