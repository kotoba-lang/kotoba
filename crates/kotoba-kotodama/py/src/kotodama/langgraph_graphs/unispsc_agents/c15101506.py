# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15101506 — Fuel oil.

This agent manages state transitions for fuel oil specifications, focusing on
viscosity, sulfur content, and safety compliance parameters such as flash point.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15101506"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    grade: str
    sulfur_ppm: float
    viscosity_cst: float
    flash_point_c: float
    is_compliant: bool


def analyze_specifications(state: State) -> dict[str, Any]:
    """Extract and normalize fuel oil chemical specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "sulfur_ppm": float(inp.get("sulfur", 500.0)),
        "viscosity_cst": float(inp.get("viscosity", 40.0)),
        "flash_point_c": float(inp.get("flash_point", 65.0)),
    }


def determine_fuel_grade(state: State) -> dict[str, Any]:
    """Assign a commercial grade based on kinematic viscosity."""
    v = state.get("viscosity_cst", 0.0)
    # Simple logic: Distillate vs Residual mapping
    grade = "No. 2 Distillate" if v < 10.0 else "No. 6 Residual"
    return {
        "log": [f"{UNISPSC_CODE}:determine_fuel_grade"],
        "grade": grade,
    }


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Verify flash point and sulfur limits for environmental and safety standards."""
    fp = state.get("flash_point_c", 0.0)
    sulfur = state.get("sulfur_ppm", 0.0)

    # Minimum flash point 60C, Max sulfur 1000ppm for this model
    compliant = fp >= 60.0 and sulfur <= 1000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance"],
        "is_compliant": compliant,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "grade": state.get("grade"),
            "compliance_status": "PASSED" if compliant else "FAILED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specifications)
_g.add_node("grade", determine_fuel_grade)
_g.add_node("verify", verify_safety_compliance)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "grade")
_g.add_edge("grade", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
