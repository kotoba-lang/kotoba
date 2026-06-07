# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174101 — Emergency Vehicle (segment 25).

Bespoke graph logic for handling emergency vehicle dispatch, equipment
readiness checks, and deployment state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174101"
UNISPSC_TITLE = "Emergency Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Emergency Vehicles
    vehicle_type: str
    dispatch_priority: int
    equipment_check_passed: bool
    siren_active: bool


def validate_dispatch(state: State) -> dict[str, Any]:
    """Validates the dispatch request and determines priority level."""
    inp = state.get("input") or {}
    v_type = inp.get("vehicle_type", "Ambulance")
    priority = inp.get("priority", 1)  # 1 is highest

    return {
        "log": [f"{UNISPSC_CODE}:validate_dispatch -> {v_type} (Priority: {priority})"],
        "vehicle_type": v_type,
        "dispatch_priority": priority,
    }


def inspect_equipment(state: State) -> dict[str, Any]:
    """Simulates a readiness check for critical emergency response equipment."""
    v_type = state.get("vehicle_type", "Ambulance")
    # Simulation logic: verify oxygen, defibrillator, or firefighting tools
    inspection_passed = v_type != "Unknown"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_equipment -> passed={inspection_passed}"],
        "equipment_check_passed": inspection_passed,
        "siren_active": inspection_passed,
    }


def deploy_response(state: State) -> dict[str, Any]:
    """Finalizes vehicle deployment and generates the outcome result."""
    ready = state.get("equipment_check_passed", False)
    priority = state.get("dispatch_priority", 3)

    return {
        "log": [f"{UNISPSC_CODE}:deploy_response -> status={'En Route' if ready else 'Service Required'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "active_dispatch": ready,
            "priority_level": priority,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_dispatch", validate_dispatch)
_g.add_node("inspect_equipment", inspect_equipment)
_g.add_node("deploy_response", deploy_response)

_g.add_edge(START, "validate_dispatch")
_g.add_edge("validate_dispatch", "inspect_equipment")
_g.add_edge("inspect_equipment", "deploy_response")
_g.add_edge("deploy_response", END)

graph = _g.compile()
