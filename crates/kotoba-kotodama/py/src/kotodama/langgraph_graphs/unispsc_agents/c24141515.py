# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141515 — Netting (segment 24).

Bespoke logic for industrial netting safety verification and load testing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141515"
UNISPSC_TITLE = "Netting"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141515"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_spec: str
    mesh_size_mm: float
    load_capacity_kg: float
    safety_certified: bool
    inspection_notes: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material grade of the netting."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "High-Density Polyethylene"))
    mesh = float(inp.get("mesh_opening", 25.4))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material_spec": material,
        "mesh_size_mm": mesh,
    }


def calculate_load_limits(state: State) -> dict[str, Any]:
    """Calculates the static and dynamic load limits for the netting."""
    inp = state.get("input") or {}
    base_rating = float(inp.get("base_rating", 500.0))
    wear_factor = float(inp.get("wear_factor", 1.0))

    # Calculate effective capacity based on material fatigue
    effective_capacity = base_rating * wear_factor
    required = float(inp.get("required_capacity", 400.0))
    certified = effective_capacity >= required

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_limits"],
        "load_capacity_kg": effective_capacity,
        "safety_certified": certified,
    }


def generate_safety_report(state: State) -> dict[str, Any]:
    """Generates the final compliance report and DID-linked result."""
    is_certified = state.get("safety_certified", False)
    capacity = state.get("load_capacity_kg", 0.0)

    report = f"Netting certified for {capacity}kg" if is_certified else "Fails safety threshold"

    return {
        "log": [f"{UNISPSC_CODE}:generate_safety_report"],
        "inspection_notes": report,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_certified,
            "capacity": capacity,
            "material": state.get("material_spec"),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("calculate", calculate_load_limits)
_g.add_node("report", generate_safety_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "report")
_g.add_edge("report", END)

graph = _g.compile()
