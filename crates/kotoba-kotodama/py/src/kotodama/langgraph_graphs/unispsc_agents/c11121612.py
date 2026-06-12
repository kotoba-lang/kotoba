# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121612"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121612"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    active_phase: str
    support_matrix: str
    surface_area_m2g: float
    is_deactivated: bool


def validate(state: State) -> dict[str, Any]:
    """Inbound validation of catalyst precursors and support structure."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate"],
        "active_phase": inp.get("active_phase", "Palladium"),
        "support_matrix": inp.get("support", "Activated Carbon"),
        "surface_area_m2g": float(inp.get("surface_area", 1100.0)),
    }


def process(state: State) -> dict[str, Any]:
    """Analyze the chemical properties and stability of the catalyst."""
    # Simulation of a deactivation check based on surface area thresholds
    area = state.get("surface_area_m2g", 0.0)
    deactivated = area < 100.0
    return {
        "log": [f"{UNISPSC_CODE}:process"],
        "is_deactivated": deactivated,
    }


def emit(state: State) -> dict[str, Any]:
    """Compile the final technical specification for the catalyst actor."""
    return {
        "log": [f"{UNISPSC_CODE}:emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "active_phase": state.get("active_phase"),
                "support_matrix": state.get("support_matrix"),
                "surface_area_m2g": state.get("surface_area_m2g"),
                "status": "Inactive" if state.get("is_deactivated") else "Active",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate)
_g.add_node("process", process)
_g.add_node("emit", emit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
