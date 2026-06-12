# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122352 — Bearing (segment 20).
Bespoke implementation for mechanical bearings state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122352"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122352"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    specification_verified: bool
    load_capacity_n: float
    lubrication_status: str
    tolerance_grade: str


def inspect_spec(state: State) -> dict[str, Any]:
    """Verify physical dimensions and tolerance against requirements."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    # Simple validation for inner and outer diameters
    verified = bool(dims.get("inner_diameter") and dims.get("outer_diameter"))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "specification_verified": verified,
        "tolerance_grade": inp.get("grade", "P0"),
    }


def compute_load(state: State) -> dict[str, Any]:
    """Calculate dynamic load capacity based on material and size."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    od = float(dims.get("outer_diameter", 100.0))
    id_ = float(dims.get("inner_diameter", 50.0))
    # Heuristic calculation for nominal dynamic load rating in Newtons
    capacity = (od - id_) * 150.0
    return {
        "log": [f"{UNISPSC_CODE}:compute_load"],
        "load_capacity_n": capacity,
        "lubrication_status": "sealed" if inp.get("is_sealed") else "open",
    }


def finalize_catalog(state: State) -> dict[str, Any]:
    """Finalize the bearing state and output the actor result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "verified": state.get("specification_verified", False),
            "capacity_n": state.get("load_capacity_n", 0.0),
            "lubrication": state.get("lubrication_status", "unknown"),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("compute_load", compute_load)
_g.add_node("finalize_catalog", finalize_catalog)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "compute_load")
_g.add_edge("compute_load", "finalize_catalog")
_g.add_edge("finalize_catalog", END)

graph = _g.compile()
