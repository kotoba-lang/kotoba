# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23152204"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23152204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    bearing_type: str
    dimensions_mm: dict[str, float]
    precision_rating: str
    material_grade: str
    validation_status: str


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and type of the bearing."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {"inner_dia": 25.0, "outer_dia": 52.0, "width": 15.0})
    b_type = inp.get("type", "Deep Groove Ball Bearing")

    # Simple validation: Outer diameter must be larger than inner diameter
    is_valid = dims.get("outer_dia", 0) > dims.get("inner_dia", 0)
    status = "VALID" if is_valid else "INVALID"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "bearing_type": b_type,
        "dimensions_mm": dims,
        "validation_status": status
    }


def analyze_load_capacity(state: State) -> dict[str, Any]:
    """Simulates assigning precision class and material based on inspection."""
    status = state.get("validation_status")
    # Simulation of material assignment based on validation
    material = "Chrome Steel (SAE 52100)" if status == "VALID" else "N/A"
    precision = "P6 / ABEC-3" if status == "VALID" else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_capacity"],
        "material_grade": material,
        "precision_rating": precision
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the bearing metadata and emits the result."""
    precision = state.get("precision_rating")
    is_ok = precision != "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "bearing_type": state.get("bearing_type"),
            "precision": precision,
            "certified": is_ok,
            "segment": UNISPSC_SEGMENT
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("analyze", analyze_load_capacity)
_g.add_node("certify", certify_and_emit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
