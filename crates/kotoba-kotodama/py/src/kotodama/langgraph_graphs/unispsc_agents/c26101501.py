# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101501 — Hydraulic (segment 26).

Bespoke graph logic for hydraulic power transmission systems. This agent
manages state transitions for hydraulic system validation, pressure
safety checks, and technical specification generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101501"
UNISPSC_TITLE = "Hydraulic"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Hydraulic systems
    operating_pressure_psi: float
    fluid_type: str
    safety_bypass_active: bool
    seal_integrity_score: float
    thermal_stability_verified: bool


def analyze_system_parameters(state: State) -> dict[str, Any]:
    """Analyzes incoming request parameters for hydraulic system configuration."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 2500.0))
    fluid = str(inp.get("fluid", "ISO VG 46"))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_system_parameters"],
        "operating_pressure_psi": pressure,
        "fluid_type": fluid,
        "safety_bypass_active": pressure > 3000.0,
    }


def validate_safety_constraints(state: State) -> dict[str, Any]:
    """Validates if the hydraulic system operates within safe mechanical bounds."""
    pressure = state.get("operating_pressure_psi", 0.0)
    # Simulation of a seal integrity check based on pressure and fluid type
    integrity = 0.98 if pressure < 3500.0 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_constraints"],
        "seal_integrity_score": integrity,
        "thermal_stability_verified": integrity > 0.90,
    }


def compile_technical_specs(state: State) -> dict[str, Any]:
    """Compiles the final hydraulic specification report."""
    is_safe = state.get("thermal_stability_verified", False)
    pressure = state.get("operating_pressure_psi", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:compile_technical_specs"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "APPROVED" if is_safe else "REJECTED_SAFETY_VIOLATION",
            "metrics": {
                "max_pressure": pressure,
                "fluid": state.get("fluid_type"),
                "integrity_index": state.get("seal_integrity_score"),
            },
            "did": UNISPSC_DID,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_system_parameters)
_g.add_node("validate", validate_safety_constraints)
_g.add_node("compile", compile_technical_specs)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "validate")
_g.add_edge("validate", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
