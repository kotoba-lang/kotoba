"""
saikin.cycle.v1 — LangGraph StateGraph port of saikin horizontal-transfer cycle.

ADR-2605080600 Phase 4: replaces the Zeebe BPMN `saikin_horizontal_transfer_cycle`
+ LangServer `saikin-zeebe-worker` pool. Triggered by K8s CronJob (R/PT20M)
via POST /runs.

Graph (probe → fork on signal_count → 2 mutually exclusive branches → audit-merge):
  START
    → probe_environment
    → has_signals_gate
        ├─ no_signals → END
        └─ has_signals → transfer_signal
                          → transfer_outcome_gate
                              ├─ form_colony → handoff_to_ki → END
                              └─ lyse                          → END
"""

from __future__ import annotations

from typing import Any, TypedDict


class SaikinCycleState(TypedDict, total=False):
    signalCount: int
    signals: list[Any]
    transferId: str | None
    transferStatus: str | None
    signalId: str | None
    colonyId: str | None
    memberCount: int | None
    kiAbsorbId: str | None
    kiAbsorbVertexId: str | None
    lysed: bool
    releasedAt: str | None
    ok: bool
    error: str | None


async def _probe_node(state: SaikinCycleState) -> dict:
    from kotodama.saikin_worker_main import task_probe_environment
    try:
        r = await task_probe_environment()
        return {
            "signalCount": int(r.get("signalCount", 0)),
            "signals": r.get("signals") or [],
            "ok": True,
        }
    except Exception as exc:
        return {"ok": False, "error": f"probe: {exc}"}


async def _transfer_node(state: SaikinCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.saikin_worker_main import task_transfer_signal
    try:
        r = await task_transfer_signal(signals=state.get("signals") or [])
        return {
            "transferId": r.get("transferId"),
            "transferStatus": r.get("status") or "transferred",
            "signalId": r.get("signalId"),
        }
    except Exception as exc:
        return {"ok": False, "error": f"transfer: {exc}"}


async def _form_colony_node(state: SaikinCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.saikin_worker_main import task_form_colony
    try:
        r = await task_form_colony(
            signalId=state.get("signalId"),
            transferId=state.get("transferId"),
        )
        return {
            "colonyId": r.get("colonyId"),
            "memberCount": int(r.get("memberCount", 0)),
        }
    except Exception as exc:
        return {"ok": False, "error": f"form_colony: {exc}"}


async def _handoff_node(state: SaikinCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.saikin_worker_main import task_handoff_to_ki
    try:
        r = await task_handoff_to_ki(
            colonyId=state.get("colonyId"),
            signalId=state.get("signalId"),
        )
        return {
            "kiAbsorbId": r.get("kiAbsorbId"),
            "kiAbsorbVertexId": r.get("kiAbsorbVertexId"),
        }
    except Exception as exc:
        return {"ok": False, "error": f"handoff: {exc}"}


async def _lyse_node(state: SaikinCycleState) -> dict:
    if not state.get("ok", True):
        return {}
    from kotodama.saikin_worker_main import task_lyse
    try:
        r = await task_lyse(
            signalId=state.get("signalId"),
            reason="fully-transferred",
        )
        return {
            "lysed": bool(r.get("lysed", True)),
            "releasedAt": r.get("releasedAt"),
        }
    except Exception as exc:
        return {"ok": False, "error": f"lyse: {exc}"}


def _has_signals_gate(state: SaikinCycleState) -> str:
    return "transfer" if int(state.get("signalCount", 0) or 0) > 0 else "no_signals"


def _transfer_outcome_gate(state: SaikinCycleState) -> str:
    status = state.get("transferStatus") or ""
    return "form_colony" if status == "transferred" else "lyse"


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(SaikinCycleState)
    builder.add_node("probe", _probe_node)
    builder.add_node("transfer", _transfer_node)
    builder.add_node("form_colony", _form_colony_node)
    builder.add_node("handoff", _handoff_node)
    builder.add_node("lyse", _lyse_node)

    builder.set_entry_point("probe")
    builder.add_conditional_edges(
        "probe",
        _has_signals_gate,
        {"transfer": "transfer", "no_signals": END},
    )
    builder.add_conditional_edges(
        "transfer",
        _transfer_outcome_gate,
        {"form_colony": "form_colony", "lyse": "lyse"},
    )
    builder.add_edge("form_colony", "handoff")
    builder.add_edge("handoff", END)
    builder.add_edge("lyse", END)

    return builder.compile()
