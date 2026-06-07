# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121310"
UNISPSC_TITLE = "Linear Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121310"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    load_capacity_kn: float
    precision_class: str
    rail_type: str
    seal_integrity_verified: bool


def assess_mechanical_load(state: State) -> dict[str, Any]:
    """Calculates the dynamic load requirement for the linear motion system."""
    inp = state.get("input") or {}
    # Use provided load or a default industrial standard
    load = float(inp.get("load_kn", 12.5))
    return {
        "log": [f"{UNISPSC_CODE}:assess_mechanical_load"],
        "load_capacity_kn": load,
    }


def configure_bearing_geometry(state: State) -> dict[str, Any]:
    """Selects rail profile and precision grade based on load requirements."""
    load = state.get("load_capacity_kn", 0.0)
    # Heuristic for rail selection based on force magnitude
    rtype = "Profile Rail" if load > 10.0 else "Round Shaft"
    pclass = "P5" if load > 20.0 else "P0"
    return {
        "log": [f"{UNISPSC_CODE}:configure_bearing_geometry"],
        "rail_type": rtype,
        "precision_class": pclass,
        "seal_integrity_verified": True,
    }


def finalize_linear_specification(state: State) -> dict[str, Any]:
    """Assembles the final engineering data sheet for the linear bearing unit."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_linear_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "configuration": {
                "rail_type": state.get("rail_type"),
                "precision_grade": state.get("precision_class"),
                "dynamic_load_kn": state.get("load_capacity_kn"),
                "environment_protection": "Sealed" if state.get("seal_integrity_verified") else "Open",
            },
            "system_status": "configured",
        },
    }


_g = StateGraph(State)
_g.add_node("assess_mechanical_load", assess_mechanical_load)
_g.add_node("configure_bearing_geometry", configure_bearing_geometry)
_g.add_node("finalize_linear_specification", finalize_linear_specification)

_g.add_edge(START, "assess_mechanical_load")
_g.add_edge("assess_mechanical_load", "configure_bearing_geometry")
_g.add_edge("configure_bearing_geometry", "finalize_linear_specification")
_g.add_edge("finalize_linear_specification", END)

graph = _g.compile()
