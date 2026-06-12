# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181603 — A G V (Automated Guided Vehicles).
Bespoke LangGraph logic for industrial AGV mission management and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181603"
UNISPSC_TITLE = "A G V"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke AGV domain fields
    mission_id: str
    battery_level: float
    load_weight_kg: float
    safety_clearance: bool
    navigation_status: str


def initialize_mission(state: State) -> dict[str, Any]:
    """Parses mission data and checks vehicle availability."""
    inp = state.get("input") or {}
    mission_id = inp.get("mission_id", "M-UNKNOWN")
    weight = float(inp.get("weight", 0.0))

    # Default battery level for a new mission cycle
    return {
        "log": [f"{UNISPSC_CODE}:initialize_mission: id={mission_id}"],
        "mission_id": mission_id,
        "load_weight_kg": weight,
        "battery_level": 88.5,
    }


def safety_diagnostics(state: State) -> dict[str, Any]:
    """Performs safety checks including battery level and sensor clearance."""
    battery = state.get("battery_level", 0.0)
    weight = state.get("load_weight_kg", 0.0)

    # Requirement: Battery > 15% and Load <= 1500kg
    battery_ok = battery > 15.0
    load_ok = weight <= 1500.0

    clearance = battery_ok and load_ok
    status = "READY" if clearance else "FAIL_SAFETY"

    return {
        "log": [f"{UNISPSC_CODE}:safety_diagnostics: battery_ok={battery_ok}, load_ok={load_ok}"],
        "safety_clearance": clearance,
        "navigation_status": status,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Compiles the final dispatch authorization for the AGV."""
    clearance = state.get("safety_clearance", False)
    mission_id = state.get("mission_id", "")

    outcome = "AUTHORIZED" if clearance else "DENIED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch: outcome={outcome}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_id": mission_id,
            "status": outcome,
            "ok": clearance,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_mission)
_g.add_node("diagnostics", safety_diagnostics)
_g.add_node("dispatch", finalize_dispatch)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "diagnostics")
_g.add_edge("diagnostics", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
