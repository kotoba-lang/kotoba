# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142500 — Rack (segment 20).

Bespoke LangGraph implementation for managing well-drilling pipe racks.
This agent handles structural specification validation, load capacity
assessment, and safety certification for equipment used in mining and
well completion operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142500"
UNISPSC_TITLE = "Rack"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Rack" (Well Drilling Equipment)
    material_grade: str
    max_load_kn: float
    current_occupancy: int
    safety_factor: float
    structural_verified: bool


def inspect_inventory(state: State) -> dict[str, Any]:
    """Inspects the physical specifications of the rack assembly."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    material = specs.get("material", "ASTM-A36")
    capacity = specs.get("capacity_kn", 500.0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_inventory"],
        "material_grade": material,
        "max_load_kn": capacity,
        "structural_verified": capacity > 0
    }


def evaluate_load_dynamics(state: State) -> dict[str, Any]:
    """Calculates load distribution and safety margins."""
    inp = state.get("input") or {}
    occupancy = inp.get("load_count", 0)
    max_load = state.get("max_load_kn", 1.0)

    # Simple logic: safety factor decreases as occupancy increases
    load_per_unit = 10.5  # kN per pipe unit
    total_load = occupancy * load_per_unit
    safety_factor = max_load / (total_load if total_load > 0 else 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_load_dynamics"],
        "current_occupancy": occupancy,
        "safety_factor": round(safety_factor, 2)
    }


def certify_disposition(state: State) -> dict[str, Any]:
    """Finalizes the rack status and issues a compliance manifest."""
    is_safe = state.get("safety_factor", 0.0) >= 1.5 and state.get("structural_verified")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "status": "OPERATIONAL" if is_safe else "RESTRICTED",
        "metrics": {
            "safety_factor": state.get("safety_factor"),
            "material": state.get("material_grade")
        },
        "ok": is_safe
    }

    return {
        "log": [f"{UNISPSC_CODE}:certify_disposition"],
        "result": res
    }


_g = StateGraph(State)

_g.add_node("inspect_inventory", inspect_inventory)
_g.add_node("evaluate_load_dynamics", evaluate_load_dynamics)
_g.add_node("certify_disposition", certify_disposition)

_g.add_edge(START, "inspect_inventory")
_g.add_edge("inspect_inventory", "evaluate_load_dynamics")
_g.add_edge("evaluate_load_dynamics", "certify_disposition")
_g.add_edge("certify_disposition", END)

graph = _g.compile()
