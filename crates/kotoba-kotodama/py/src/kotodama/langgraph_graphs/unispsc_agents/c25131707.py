# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131707 — Aircraft (segment 25).

Bespoke graph logic for aircraft lifecycle management, including
airworthiness verification, registration checks, and dispatch authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131707"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131707"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra Aircraft domain fields
    airworthiness_certified: bool
    registration_status: str
    maintenance_due: bool
    flight_ready: bool


def inspect_airworthiness(state: State) -> dict[str, Any]:
    """Node to check the physical and mechanical integrity of the aircraft."""
    inp = state.get("input") or {}
    hours = inp.get("airframe_hours", 0)
    # Aircraft requires overhaul after 5000 hours in this simplified logic
    needs_maintenance = hours > 5000
    return {
        "log": [f"{UNISPSC_CODE}:inspect_airworthiness"],
        "airworthiness_certified": not needs_maintenance,
        "maintenance_due": needs_maintenance,
    }


def verify_registration(state: State) -> dict[str, Any]:
    """Node to verify the registration and legal status of the aircraft."""
    inp = state.get("input") or {}
    tail_number = inp.get("tail_number", "")
    # Simple validation: tail number must be at least 4 characters and start with a letter
    is_valid = len(tail_number) > 3 and tail_number[0].isalpha()
    return {
        "log": [f"{UNISPSC_CODE}:verify_registration"],
        "registration_status": "VALID" if is_valid else "INVALID",
    }


def authorize_flight(state: State) -> dict[str, Any]:
    """Final node to aggregate checks and authorize flight dispatch."""
    is_certified = state.get("airworthiness_certified", False)
    is_registered = state.get("registration_status") == "VALID"
    ready = is_certified and is_registered

    return {
        "log": [f"{UNISPSC_CODE}:authorize_flight"],
        "flight_ready": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "dispatch_status": "AUTHORIZED" if ready else "DENIED",
            "ok": ready,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_airworthiness", inspect_airworthiness)
_g.add_node("verify_registration", verify_registration)
_g.add_node("authorize_flight", authorize_flight)

_g.add_edge(START, "inspect_airworthiness")
_g.add_edge("inspect_airworthiness", "verify_registration")
_g.add_edge("verify_registration", "authorize_flight")
_g.add_edge("authorize_flight", END)

graph = _g.compile()
