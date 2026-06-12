# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101706 — Aircraft (segment 26).

Bespoke graph logic for aircraft procurement and operational readiness.
This agent handles airworthiness verification, logistical planning, and dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101706"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Aircraft
    tail_number: str
    maintenance_status: str
    fuel_load_kg: float
    airworthiness_certified: bool


def verify_airworthiness(state: State) -> dict[str, Any]:
    """Validates tail number registration and maintenance logs."""
    inp = state.get("input") or {}
    tail_num = inp.get("tail_number", "N0000")
    # Heuristic: Valid tail numbers for this mock must start with 'N'
    is_valid = tail_num.startswith("N")

    return {
        "log": [f"{UNISPSC_CODE}:verify_airworthiness({tail_num})"],
        "tail_number": tail_num,
        "maintenance_status": "CURRENT" if is_valid else "OVERDUE",
        "airworthiness_certified": is_valid,
    }


def compute_flight_logistics(state: State) -> dict[str, Any]:
    """Calculates fuel requirements and payload capacity."""
    inp = state.get("input") or {}
    distance = inp.get("distance_nm", 500.0)
    # Basic burn rate simulation
    fuel_needed = distance * 12.5

    return {
        "log": [f"{UNISPSC_CODE}:compute_flight_logistics({distance}nm)"],
        "fuel_load_kg": fuel_needed,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Finalizes the aircraft state for procurement or operational assignment."""
    certified = state.get("airworthiness_certified", False)
    maint = state.get("maintenance_status", "UNKNOWN")
    tail = state.get("tail_number", "N0000")

    ready = certified and (maint == "CURRENT")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "fuel_required": state.get("fuel_load_kg"),
            "operational_ready": ready,
            "status": "APPROVED" if ready else "GROUNDED",
        },
    }


_g = StateGraph(State)

_g.add_node("verify_airworthiness", verify_airworthiness)
_g.add_node("compute_flight_logistics", compute_flight_logistics)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "verify_airworthiness")
_g.add_edge("verify_airworthiness", "compute_flight_logistics")
_g.add_edge("compute_flight_logistics", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
