# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111812"
UNISPSC_TITLE = "Basin"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111812"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material: str
    capacity_liters: float
    dimensions_mm: dict[str, float]
    drainage_type: str
    is_industrial: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the input specifications for the storage basin."""
    inp = state.get("input") or {}
    mat = inp.get("material", "polyethylene")
    dims = inp.get("dimensions", {"length": 1200, "width": 800, "depth": 600})
    return {
        "log": [f"{UNISPSC_CODE}:validate_spec -> {mat} basin"],
        "material": mat,
        "dimensions_mm": dims,
        "is_industrial": inp.get("industrial", True),
    }


def compute_volume(state: State) -> dict[str, Any]:
    """Computes the liquid capacity based on physical dimensions."""
    dims = state.get("dimensions_mm", {})
    l = dims.get("length", 0)
    w = dims.get("width", 0)
    d = dims.get("depth", 0)
    # Convert mm^3 to Liters
    vol = (l * w * d) / 1_000_000.0
    drain = "heavy_duty_reinforced" if vol > 500 else "standard_gravity"
    return {
        "log": [f"{UNISPSC_CODE}:compute_volume -> {vol:.2f}L capacity"],
        "capacity_liters": vol,
        "drainage_type": drain,
    }


def finalize_basin(state: State) -> dict[str, Any]:
    """Finalizes the basin configuration for the inventory system."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_basin"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "capacity_liters": state.get("capacity_liters"),
                "material": state.get("material"),
                "drainage": state.get("drainage_type"),
                "industrial_grade": state.get("is_industrial"),
            },
            "status": "configured",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_spec", validate_spec)
_g.add_node("compute_volume", compute_volume)
_g.add_node("finalize_basin", finalize_basin)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "compute_volume")
_g.add_edge("compute_volume", "finalize_basin")
_g.add_edge("finalize_basin", END)

graph = _g.compile()
