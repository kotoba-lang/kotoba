# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101627 — Trolley (segment 24).

Bespoke LangGraph logic for managing trolley assets, including safety
inspections, load validation, and dispatch readiness for material handling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101627"
UNISPSC_TITLE = "Trolley"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101627"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Bespoke domain state for Trolley
    load_capacity_kg: float
    current_load_kg: float
    maintenance_status: str
    safety_check_passed: bool
    destination_aisle: str


def perform_safety_check(state: State) -> dict[str, Any]:
    """Checks the structural integrity and maintenance logs of the trolley."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 250.0)
    # Simulate a maintenance check based on last service days
    has_recent_service = inp.get("last_service_days", 0) < 180
    status = "OPERATIONAL" if has_recent_service else "MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:safety_check:{status}"],
        "load_capacity_kg": capacity,
        "maintenance_status": status,
        "safety_check_passed": has_recent_service,
    }


def validate_payload(state: State) -> dict[str, Any]:
    """Validates that the current load does not exceed the trolley's capacity."""
    inp = state.get("input") or {}
    load = inp.get("load_weight", 0.0)
    capacity = state.get("load_capacity_kg", 250.0)
    aisle = inp.get("aisle", "GENERAL_STORAGE")

    overloaded = load > capacity
    safety_ok = state.get("safety_check_passed", False) and not overloaded

    return {
        "log": [f"{UNISPSC_CODE}:validate_payload:overloaded={overloaded}"],
        "current_load_kg": load,
        "destination_aisle": aisle,
        "safety_check_passed": safety_ok,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Prepares the final result based on safety and payload validation."""
    is_ready = state.get("safety_check_passed", False)
    load = state.get("current_load_kg", 0.0)
    cap = state.get("load_capacity_kg", 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch:ready={is_ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "dispatch_ready": is_ready,
            "metrics": {
                "weight_kg": load,
                "utilization_pct": (load / cap) * 100,
                "maintenance": state.get("maintenance_status")
            },
            "routing": state.get("destination_aisle")
        },
    }


_g = StateGraph(State)
_g.add_node("safety_check", perform_safety_check)
_g.add_node("validate_payload", validate_payload)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "safety_check")
_g.add_edge("safety_check", "validate_payload")
_g.add_edge("validate_payload", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
