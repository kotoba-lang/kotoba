# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271701 — Blow Pipe (segment 23).

Bespoke graph logic for industrial blow pipe validation and flow calibration.
This agent handles the lifecycle of a blow pipe operation, including
specification verification and safety checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271701"
UNISPSC_TITLE = "Blow Pipe"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Blow Pipe
    wall_thickness_mm: float
    material_grade: str
    max_pressure_rating: float
    inspection_passed: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical properties of the blow pipe."""
    inp = state.get("input") or {}
    thickness = float(inp.get("thickness", 5.0))
    grade = str(inp.get("grade", "Standard-Steel"))

    # Simple logic: blow pipes must have minimum thickness
    passed = thickness >= 3.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications (passed={passed})"],
        "wall_thickness_mm": thickness,
        "material_grade": grade,
        "inspection_passed": passed
    }


def calculate_flow_capacity(state: State) -> dict[str, Any]:
    """Calculates safe operating pressure based on material and thickness."""
    thickness = state.get("wall_thickness_mm", 0.0)
    # Heuristic calculation for pressure rating
    rating = thickness * 15.5

    return {
        "log": [f"{UNISPSC_CODE}:calculate_flow_capacity (rating={rating:.2f} PSI)"],
        "max_pressure_rating": rating
    }


def certify_operation(state: State) -> dict[str, Any]:
    """Generates the final certification and result object."""
    is_ok = state.get("inspection_passed", False)
    rating = state.get("max_pressure_rating", 0.0)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "ok": is_ok,
        "operational_specs": {
            "material": state.get("material_grade"),
            "max_psi": rating,
            "certified": is_ok
        }
    }

    return {
        "log": [f"{UNISPSC_CODE}:certify_operation"],
        "result": res
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("calculate", calculate_flow_capacity)
_g.add_node("certify", certify_operation)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
