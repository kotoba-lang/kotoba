# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23111501 — Hydraulic Spec (segment 23).

This module provides bespoke logic for validating and processing hydraulic
specifications within the Etz Hayyim actor framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23111501"
UNISPSC_TITLE = "Hydraulic Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23111501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Hydraulic domain fields
    operating_pressure_psi: int
    nominal_flow_rate_gpm: float
    viscosity_grade: str
    safety_margin_verified: bool


def analyze_input(state: State) -> dict[str, Any]:
    """Extracts and normalizes hydraulic parameters from the input payload."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:analyze_input"],
        "operating_pressure_psi": int(inp.get("pressure", 2500)),
        "nominal_flow_rate_gpm": float(inp.get("flow", 10.0)),
        "viscosity_grade": str(inp.get("viscosity", "ISO VG 46")),
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Verifies that the requested pressure is within safe operating margins."""
    pressure = state.get("operating_pressure_psi", 0)
    # Threshold for standard hydraulic components
    is_safe = pressure <= 4500
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "safety_margin_verified": is_safe,
    }


def compile_specification(state: State) -> dict[str, Any]:
    """Finalizes the technical specification and sets the agent result."""
    safe = state.get("safety_margin_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:compile_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "pressure_psi": state.get("operating_pressure_psi"),
                "flow_gpm": state.get("nominal_flow_rate_gpm"),
                "fluid_viscosity": state.get("viscosity_grade"),
            },
            "compliance": "CERTIFIED" if safe else "REJECTED_HIGH_PRESSURE",
            "ok": safe,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_input)
_g.add_node("validate", validate_safety)
_g.add_node("compile", compile_specification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "validate")
_g.add_edge("validate", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
