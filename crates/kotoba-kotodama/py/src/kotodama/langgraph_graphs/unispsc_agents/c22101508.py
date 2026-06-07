# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101508 — Bearing (segment 22).

Bespoke graph for bearing specification validation and load capacity analysis
within the Building and Construction Machinery context.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101508"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Bearing
    bearing_type: str
    material_grade: str
    load_rating_kn: float
    dimensions_mm: dict[str, float]
    spec_verified: bool


def validate_bearing_specs(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the bearing."""
    inp = state.get("input") or {}
    b_type = inp.get("bearing_type", "unspecified")
    dims = inp.get("dimensions", {"id": 0.0, "od": 0.0, "w": 0.0})

    log_entry = f"{UNISPSC_CODE}:validate_bearing_specs - {b_type}"
    return {
        "log": [log_entry],
        "bearing_type": b_type,
        "dimensions_mm": dims,
        "spec_verified": all(v > 0 for v in dims.values()) and b_type != "unspecified"
    }


def analyze_load_capacity(state: State) -> dict[str, Any]:
    """Calculates or verifies load capacity based on material and type."""
    material = state.get("input", {}).get("material", "standard_steel")
    # Simulated load rating calculation based on type
    base_rating = 15.5 if state.get("bearing_type") == "roller" else 10.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_capacity - {material}"],
        "material_grade": material,
        "load_rating_kn": base_rating
    }


def finalize_bearing_record(state: State) -> dict[str, Any]:
    """Finalizes the bearing data for the construction equipment registry."""
    verified = state.get("spec_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_bearing_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "verified": verified,
            "summary": {
                "type": state.get("bearing_type"),
                "load_kn": state.get("load_rating_kn"),
                "material": state.get("material_grade"),
                "dimensions": state.get("dimensions_mm")
            }
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_bearing_specs)
_g.add_node("analyze", analyze_load_capacity)
_g.add_node("finalize", finalize_bearing_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
