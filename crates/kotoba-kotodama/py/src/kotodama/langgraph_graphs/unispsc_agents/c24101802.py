# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101802 — Material Handling Equipment (segment 24).

Bespoke graph for hand trucks and pallet jacks, managing load specifications,
safety inspections, and warehouse zone deployment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101802"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for material handling equipment
    load_capacity_kg: int
    hydraulic_pressure_psi: float
    safety_inspection_passed: bool
    assigned_zone: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Checks the equipment load capacity against requested requirements."""
    inp = state.get("input") or {}
    requested_load = inp.get("load_weight", 0)

    # Standard pallet truck capacity is usually around 2000-2500kg
    standard_capacity = 2500
    is_valid = requested_load <= standard_capacity

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "load_capacity_kg": standard_capacity,
        "safety_inspection_passed": is_valid,
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Simulates a check of hydraulic systems and structural integrity."""
    is_valid = state.get("safety_inspection_passed", False)
    pressure = 2200.0 if is_valid else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check"],
        "hydraulic_pressure_psi": pressure,
        "assigned_zone": "Active-Floor" if is_valid else "Maintenance-Bay",
    }


def authorize_deployment(state: State) -> dict[str, Any]:
    """Finalizes the deployment record and prepares the actor result."""
    is_safe = state.get("safety_inspection_passed", False)
    zone = state.get("assigned_zone", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_deployment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ready" if is_safe else "offline",
            "deployment_zone": zone,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("inspect", perform_safety_check)
_g.add_node("authorize", authorize_deployment)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
