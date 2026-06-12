# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241612 — Press Brake (segment 23).
Bespoke graph for sheet metal bending operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241612"
UNISPSC_TITLE = "Press Brake"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241612"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Press Brake
    material_type: str
    thickness_mm: float
    bend_angle_deg: float
    required_tonnage: float
    safety_check_passed: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the input material specifications and safety constraints."""
    inp = state.get("input") or {}
    m_type = str(inp.get("material", "carbon_steel"))
    thickness = float(inp.get("thickness", 0.0))
    angle = float(inp.get("angle", 90.0))

    # Simple validation: thickness within machine capacity (e.g. up to 25mm)
    passed = 0.1 <= thickness <= 25.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "material_type": m_type,
        "thickness_mm": thickness,
        "bend_angle_deg": angle,
        "safety_check_passed": passed
    }


def calculate_tonnage(state: State) -> dict[str, Any]:
    """Calculates required force based on material thickness and angle."""
    thickness = state.get("thickness_mm", 0.0)
    # Simple tonnage heuristic: Force (Tons) = (thickness^2 * 8) / V-opening
    # Assuming constant V-opening for this model
    tonnage = (thickness ** 2) * 8.0 if state.get("safety_check_passed") else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_tonnage"],
        "required_tonnage": tonnage
    }


def execute_bend(state: State) -> dict[str, Any]:
    """Finalizes the operation and emits the result metadata."""
    ok = state.get("safety_check_passed", False)
    tonnage = state.get("required_tonnage", 0.0)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "status": "success" if ok else "inhibited_by_safety",
        "metrics": {
            "applied_tonnage": tonnage,
            "angle": state.get("bend_angle_deg")
        },
        "ok": ok,
    }

    return {
        "log": [f"{UNISPSC_CODE}:execute_bend"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("calculate", calculate_tonnage)
_g.add_node("execute", execute_bend)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
