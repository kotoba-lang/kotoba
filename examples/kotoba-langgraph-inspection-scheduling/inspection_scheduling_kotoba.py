"""inspection_scheduling_kotoba — InspectionSchedulingCell compiled to WASM.

Port of `20-actors/gov-municipality/cells/inspection_scheduling/cell.py`
onto the WASM-native `kotoba_langgraph` API so it compiles to a kotoba-node component.

Build:
    ../../scripts/build-pywasm.sh inspection_scheduling_kotoba.py -o inspection_scheduling_kotoba.wasm
"""

from __future__ import annotations
from typing import Any, TypedDict
import wit_world

from kotoba_langgraph import StateGraph, KotobaCheckpointer, START, END, handle_invoke
import kotoba_langgraph._cbor  # noqa: F401
import kotoba_langgraph._entry  # noqa: F401

class InspectionStateDict(TypedDict, total=False):
    projectId: str
    inspection_state: dict[str, Any]
    next_node: str
    inspection_schedule_record: dict[str, Any]

def _initialize_state(state: InspectionStateDict) -> InspectionStateDict:
    return {"inspection_state": {"phase": "init", "projectId": state.get("projectId", "unknown"), "completionPct": 0}, "next_node": "fetch"}

def _fetch_permit_status(state: InspectionStateDict) -> InspectionStateDict:
    return {"inspection_state": {**state.get("inspection_state", {}), "phase": "permit_verified", "completionPct": 25}, "next_node": "rules"}

def _jurisdiction_rules(state: InspectionStateDict) -> InspectionStateDict:
    mock_schedule = {"foundation_inspection": "2026-06-20", "structural_inspection": "2026-07-15", "mep_inspection": "2026-08-10", "finishing_inspection": "2026-09-05", "final_inspection": "2026-09-20"}
    return {"inspection_state": {**state.get("inspection_state", {}), "phase": "schedule_ready", "schedule": mock_schedule, "completionPct": 75}, "next_node": "emit"}

def _emit_schedule(state: InspectionStateDict) -> InspectionStateDict:
    return {"inspection_state": {**state.get("inspection_state", {}), "phase": "complete", "completionPct": 100}, "inspection_schedule_record": {"projectId": state.get("inspection_state", {}).get("projectId"), "schedule": state.get("inspection_state", {}).get("schedule", {})}, "next_node": "end"}

_g = StateGraph(InspectionStateDict)
_g.add_node("init", _initialize_state)
_g.add_node("fetch", _fetch_permit_status)
_g.add_node("rules", _jurisdiction_rules)
_g.add_node("emit", _emit_schedule)
_g.add_edge(START, "init")
_g.add_edge("init", "fetch")
_g.add_edge("fetch", "rules")
_g.add_edge("rules", "emit")
_g.add_edge("emit", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, compiled)
