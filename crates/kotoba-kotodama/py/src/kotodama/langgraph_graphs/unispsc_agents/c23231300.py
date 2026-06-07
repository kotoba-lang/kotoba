# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231300"
UNISPSC_TITLE = "Press Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Press Machine
    safety_interlock_active: bool
    clamping_force_kn: float
    cycle_time_seconds: float
    stroke_depth_mm: float
    tooling_id: str


def initialize_safety(state: State) -> dict[str, Any]:
    """Verify safety protocols and identify tooling."""
    inp = state.get("input") or {}
    tooling = inp.get("tooling_id", "STAMP-23-A")
    # Simulation of safety check logic
    is_safe = inp.get("emergency_stop_tripped", False) is False
    return {
        "log": [f"{UNISPSC_CODE}:initialize_safety"],
        "safety_interlock_active": is_safe,
        "tooling_id": tooling,
    }


def calibrate_and_clamp(state: State) -> dict[str, Any]:
    """Determine necessary clamping force based on material specs."""
    if not state.get("safety_interlock_active"):
        return {"log": [f"{UNISPSC_CODE}:calibrate_and_clamp:safety_failure_abort"]}

    inp = state.get("input") or {}
    material_gauge = float(inp.get("material_gauge_mm", 2.0))
    # Force calculation: 250kN per mm of gauge for this hypothetical press
    required_force = material_gauge * 250.0

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_and_clamp:success"],
        "clamping_force_kn": min(required_force, 1500.0),
    }


def execute_cycle(state: State) -> dict[str, Any]:
    """Perform the mechanical press stroke."""
    force = state.get("clamping_force_kn", 0.0)
    if force <= 0:
        return {"log": [f"{UNISPSC_CODE}:execute_cycle:skip_no_force"]}

    # Mechanical simulation of displacement and time
    depth = 12.5 + (force / 100.0)
    duration = 0.5 + (force / 2000.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_cycle:complete"],
        "stroke_depth_mm": depth,
        "cycle_time_seconds": duration,
    }


def emit_production_data(state: State) -> dict[str, Any]:
    """Package the execution metrics for the actor response."""
    success = state.get("safety_interlock_active", False) and state.get("stroke_depth_mm", 0) > 0
    return {
        "log": [f"{UNISPSC_CODE}:emit_production_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "force_kn": state.get("clamping_force_kn"),
                "depth_mm": state.get("stroke_depth_mm"),
                "duration_s": state.get("cycle_time_seconds"),
                "tooling": state.get("tooling_id"),
            },
            "status": "SUCCESS" if success else "OPERATIONAL_FAILURE",
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_safety", initialize_safety)
_g.add_node("calibrate_and_clamp", calibrate_and_clamp)
_g.add_node("execute_cycle", execute_cycle)
_g.add_node("emit_production_data", emit_production_data)

_g.add_edge(START, "initialize_safety")
_g.add_edge("initialize_safety", "calibrate_and_clamp")
_g.add_edge("calibrate_and_clamp", "execute_cycle")
_g.add_edge("execute_cycle", "emit_production_data")
_g.add_edge("emit_production_data", END)

graph = _g.compile()
