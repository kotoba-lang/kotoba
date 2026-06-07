# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101601 — Tiller (segment 21).

Bespoke logic for agricultural soil preparation machinery. This agent
handles equipment inspection, depth calibration based on soil density,
and operation logging for tilling tasks.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101601"
UNISPSC_TITLE = "Tiller"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Tiller machinery
    soil_density_kpa: float
    target_depth_mm: int
    blade_integrity_score: float
    safety_bypass_active: bool


def inspect_hardware(state: State) -> dict[str, Any]:
    """Node: Validates the physical condition of the tiller blades and safety systems."""
    inp = state.get("input") or {}
    # Simulate hardware check: defaults to high integrity unless specified
    integrity = float(inp.get("initial_blade_check", 0.95))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "blade_integrity_score": integrity,
        "safety_bypass_active": False,
    }


def calibrate_operation(state: State) -> dict[str, Any]:
    """Node: Determines optimal tilling depth based on provided soil density."""
    inp = state.get("input") or {}
    density = float(inp.get("soil_density", 120.0))

    # Simple logic: Harder soil requires shallower initial passes
    if density > 200.0:
        depth = 100
    elif density > 100.0:
        depth = 200
    else:
        depth = 300

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_operation"],
        "soil_density_kpa": density,
        "target_depth_mm": depth,
    }


def execute_tilling_sequence(state: State) -> dict[str, Any]:
    """Node: Finalizes the tilling parameters and prepares the telemetry result."""
    integrity = state.get("blade_integrity_score", 0.0)
    depth = state.get("target_depth_mm", 0)

    operational_status = "nominal" if integrity > 0.7 else "maintenance_required"

    return {
        "log": [f"{UNISPSC_CODE}:execute_tilling_sequence"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "parameters": {
                "depth_mm": depth,
                "soil_kpa": state.get("soil_density_kpa"),
            },
            "telemetry": {
                "status": operational_status,
                "integrity": integrity,
                "ok": integrity > 0.5,
            },
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_hardware)
_g.add_node("calibrate", calibrate_operation)
_g.add_node("execute", execute_tilling_sequence)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
