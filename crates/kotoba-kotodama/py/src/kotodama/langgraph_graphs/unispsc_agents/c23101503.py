# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101503 — Broaching (segment 23).

Bespoke LangGraph implementation for broaching operations, handling the
sequential removal of material using a toothed tool to achieve precise
internal or external surface finishes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101503"
UNISPSC_TITLE = "Broaching"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Broaching
    tool_geometry_id: str
    material_hardness: float
    surface_finish_ra: float
    cut_velocity: float
    is_dimensional_valid: bool


def validate_setup(state: State) -> dict[str, Any]:
    """Validates the broaching tool configuration and material compatibility."""
    inp = state.get("input") or {}
    tool_id = inp.get("tool_id", "standard-pull-broach")
    hardness = float(inp.get("hardness", 20.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_setup: tool={tool_id}, hardness={hardness}"],
        "tool_geometry_id": tool_id,
        "material_hardness": hardness,
    }


def execute_cut(state: State) -> dict[str, Any]:
    """Simulates the linear broaching pass and calculates resulting finish."""
    # Logic: Higher hardness or specific tool geometries affect the finish
    velocity = 5.0  # m/min
    finish = 1.6 if state.get("material_hardness", 0) < 30 else 3.2

    return {
        "log": [f"{UNISPSC_CODE}:execute_cut: velocity={velocity}m/min, Ra={finish}"],
        "surface_finish_ra": finish,
        "cut_velocity": velocity,
        "is_dimensional_valid": True
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Final inspection of the broached surface and result packaging."""
    valid = state.get("is_dimensional_valid", False)
    finish = state.get("surface_finish_ra", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_emit: inspection_pass={valid}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "surface_finish_ra": finish,
                "velocity": state.get("cut_velocity"),
                "status": "COMPLETED" if valid else "REJECTED"
            },
            "ok": valid,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_setup", validate_setup)
_g.add_node("execute_cut", execute_cut)
_g.add_node("verify_and_emit", verify_and_emit)

_g.add_edge(START, "validate_setup")
_g.add_edge("validate_setup", "execute_cut")
_g.add_edge("execute_cut", "verify_and_emit")
_g.add_edge("verify_and_emit", END)

graph = _g.compile()
