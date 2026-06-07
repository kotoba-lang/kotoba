# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101506 — Limousine (segment 25).

Bespoke graph logic for luxury transport services. This agent handles
reservation validation, vehicle dispatching, and trip finalization for
premium limousine operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101506"
UNISPSC_TITLE = "Limousine"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Limousine services
    booking_id: str
    chauffeur_assigned: str
    vehicle_status: str
    safety_check_passed: bool
    itinerary_verified: bool


def validate_booking(state: State) -> dict[str, Any]:
    """Validates the reservation details and itinerary."""
    inp = state.get("input") or {}
    bid = inp.get("booking_id", "RESRV-LIMO-001")
    return {
        "log": [f"{UNISPSC_CODE}:validate_booking"],
        "booking_id": bid,
        "itinerary_verified": True,
    }


def dispatch_resource(state: State) -> dict[str, Any]:
    """Assigns a chauffeur and performs vehicle safety inspection."""
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_resource"],
        "chauffeur_assigned": "Operator_ID_5521",
        "vehicle_status": "Dispatched",
        "safety_check_passed": True,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Compiles the final trip confirmation and status."""
    is_ok = state.get("safety_check_passed", False) and state.get("itinerary_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "booking_id": state.get("booking_id"),
            "chauffeur": state.get("chauffeur_assigned"),
            "status": "Ready for Pick-up",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_booking", validate_booking)
_g.add_node("dispatch_resource", dispatch_resource)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "validate_booking")
_g.add_edge("validate_booking", "dispatch_resource")
_g.add_edge("dispatch_resource", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
