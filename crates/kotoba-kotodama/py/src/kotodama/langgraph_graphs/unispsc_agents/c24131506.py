# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131506 — Tank (segment 24).

This agent provides bespoke logic for the lifecycle management and safety
certification of industrial storage tanks, including volume calibration,
material verification, and pressure-based integrity assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131506"
UNISPSC_TITLE = "Tank"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Tank lifecycle
    capacity_liters: float
    material_grade: str
    seal_integrity: bool
    inspection_passed: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Calculates tank capacity and validates material specifications."""
    inp = state.get("input") or {}
    radius = float(inp.get("radius_meters", 1.0))
    height = float(inp.get("height_meters", 2.0))
    # Approximation of cylindrical tank volume (V = pi * r^2 * h)
    volume_m3 = 3.14159 * (radius**2) * height
    capacity = volume_m3 * 1000.0  # Convert to liters

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "capacity_liters": round(capacity, 2),
        "material_grade": str(inp.get("material", "SS316L")),
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Simulates a pressure and seal integrity test on the tank structure."""
    inp = state.get("input") or {}
    test_pressure = float(inp.get("test_pressure_psi", 0))
    design_pressure = float(inp.get("design_pressure_psi", 100))

    # Safety margin: Pass if test pressure is within 1.5x design pressure
    passed = test_pressure > 0 and test_pressure <= (design_pressure * 1.5)

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check"],
        "seal_integrity": True,
        "inspection_passed": passed,
    }


def issue_certification(state: State) -> dict[str, Any]:
    """Generates the final certification manifest for the tank actor."""
    passed = state.get("inspection_passed", False)
    capacity = state.get("capacity_liters", 0.0)
    material = state.get("material_grade", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:issue_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "capacity_l": capacity,
                "material": material,
            },
            "certification": "APPROVED" if passed else "REJECTED",
            "compliance_segment": UNISPSC_SEGMENT,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("safety_check", perform_safety_check)
_g.add_node("certify", issue_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "safety_check")
_g.add_edge("safety_check", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
