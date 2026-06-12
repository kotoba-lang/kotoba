# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23121509 — Hydraulic Spec (segment 23).
This module provides bespoke logic for validating and generating hydraulic specifications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23121509"
UNISPSC_TITLE = "Hydraulic Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23121509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Hydraulic Spec
    pressure_psi: int
    fluid_compatibility: str
    bore_size_mm: float
    is_compliant: bool


def analyze_requirements(state: State) -> dict[str, Any]:
    """Extracts hydraulic parameters from input payload."""
    inp = state.get("input") or {}
    pressure = int(inp.get("pressure", 3000))
    fluid = str(inp.get("fluid", "Mineral Oil"))
    bore = float(inp.get("bore", 50.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_requirements"],
        "pressure_psi": pressure,
        "fluid_compatibility": fluid,
        "bore_size_mm": bore
    }


def verify_standards(state: State) -> dict[str, Any]:
    """Checks requirements against safety and engineering thresholds."""
    pressure = state.get("pressure_psi", 0)
    bore = state.get("bore_size_mm", 0.0)

    # Engineering rule: high pressure (>5000 PSI) requires specific bore tolerances
    compliance = True
    if pressure > 5000 and bore < 20.0:
        compliance = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_standards"],
        "is_compliant": compliance
    }


def generate_spec(state: State) -> dict[str, Any]:
    """Compiles the final specification result."""
    compliant = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "spec_summary": {
                "pressure_rating": state.get("pressure_psi"),
                "fluid": state.get("fluid_compatibility"),
                "bore": state.get("bore_size_mm"),
            },
            "status": "APPROVED" if compliant else "REJECTED_SAFETY_MARGIN",
            "ok": compliant
        }
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_requirements)
_g.add_node("verify", verify_standards)
_g.add_node("generate", generate_spec)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
