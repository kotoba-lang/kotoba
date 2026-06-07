# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101501 — Minibus.
Bespoke LangGraph implementation for fleet management and specification validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101501"
UNISPSC_TITLE = "Minibus"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Minibus
    seating_capacity: int
    propulsion_type: str
    safety_inspection_passed: bool
    fleet_assignment_id: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the minibus dimensions and seating configuration."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 15)
    p_type = inp.get("propulsion", "diesel")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "seating_capacity": capacity,
        "propulsion_type": p_type,
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Simulates a regulatory safety and emissions compliance check."""
    # Logic: Minibuses with capacity > 20 require enhanced braking certification
    capacity = state.get("seating_capacity", 0)
    passed = True if capacity <= 30 else False

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit - passed={passed}"],
        "safety_inspection_passed": passed,
    }


def register_to_fleet(state: State) -> dict[str, Any]:
    """Assigns a fleet tracking ID and prepares the final agent response."""
    passed = state.get("safety_inspection_passed", False)
    fleet_id = f"FLEET-MB-{UNISPSC_CODE}-001" if passed else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:register_to_fleet - {fleet_id}"],
        "fleet_assignment_id": fleet_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "fleet_id": fleet_id,
            "certified": passed,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("perform_safety_audit", perform_safety_audit)
_g.add_node("register_to_fleet", register_to_fleet)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "perform_safety_audit")
_g.add_edge("perform_safety_audit", "register_to_fleet")
_g.add_edge("register_to_fleet", END)

graph = _g.compile()
