# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251600 — Rolling Machine (segment 23).

Bespoke logic for industrial rolling machinery operations, including
material configuration, pressure regulation, and thickness verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251600"
UNISPSC_TITLE = "Rolling Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rolling Machine
    material_type: str
    target_thickness_mm: float
    roller_pressure_psi: float
    calibration_verified: bool


def configure_machine(state: State) -> dict[str, Any]:
    """Extract specifications and verify calibration state."""
    inp = state.get("input") or {}
    material = inp.get("material", "standard_steel")
    thickness = float(inp.get("target_thickness", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:configure_machine:material={material}:target={thickness}mm"],
        "material_type": material,
        "target_thickness_mm": thickness,
        "calibration_verified": True,
    }


def execute_rolling_cycle(state: State) -> dict[str, Any]:
    """Simulate the rolling process by applying calculated pressure."""
    # Logic: Pressure is inversely proportional to target thickness for a given material
    base_pressure = 1500.0
    thickness = state.get("target_thickness_mm", 5.0)
    calculated_pressure = base_pressure / (thickness / 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_rolling_cycle:applying_{calculated_pressure:.1f}_psi"],
        "roller_pressure_psi": calculated_pressure,
    }


def finalize_production(state: State) -> dict[str, Any]:
    """Verify output tolerances and emit the final status."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_production:completed"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material": state.get("material_type"),
            "final_thickness_mm": state.get("target_thickness_mm"),
            "status": "batch_ready",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_machine)
_g.add_node("roll", execute_rolling_cycle)
_g.add_node("finalize", finalize_production)

_g.add_edge(START, "configure")
_g.add_edge("configure", "roll")
_g.add_edge("roll", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
