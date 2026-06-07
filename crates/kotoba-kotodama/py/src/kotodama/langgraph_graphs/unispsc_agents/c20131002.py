# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131002 — Hydraulic (segment 20).

Bespoke logic for hydraulic system parameter verification and performance simulation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131002"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Hydraulic components
    system_pressure_psi: int
    flow_rate_gpm: float
    fluid_viscosity_cst: float
    leak_test_passed: bool
    efficiency_rating: float


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the input hydraulic specifications."""
    inp = state.get("input") or {}
    pressure = inp.get("pressure", 0)
    flow = inp.get("flow", 0.0)
    viscosity = inp.get("viscosity", 46.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "system_pressure_psi": pressure,
        "flow_rate_gpm": flow,
        "fluid_viscosity_cst": viscosity,
        "leak_test_passed": pressure < 5000,  # Simulated threshold
    }


def calculate_efficiency(state: State) -> dict[str, Any]:
    """Computes simulated volumetric efficiency based on flow and pressure."""
    pressure = state.get("system_pressure_psi", 0)
    flow = state.get("flow_rate_gpm", 0.0)

    # Dummy calculation: higher pressure slightly reduces efficiency
    base_eff = 0.95
    reduction = (pressure / 10000.0) if pressure > 0 else 0
    calculated_eff = max(0.7, base_eff - reduction) if flow > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_efficiency"],
        "efficiency_rating": round(calculated_eff, 3),
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final status result for the hydraulic agent."""
    is_safe = state.get("leak_test_passed", False)
    efficiency = state.get("efficiency_rating", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "operational" if is_safe and efficiency > 0.8 else "maintenance_required",
            "metrics": {
                "efficiency": efficiency,
                "safety_compliance": is_safe,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("process", calculate_efficiency)
_g.add_node("emit", finalize_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
