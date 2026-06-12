# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201701 — Aircraft (segment 25).

Bespoke graph logic for aircraft lifecycle management, including
airworthiness inspection, maintenance verification, and flight authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201701"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft
    tail_number: str
    airworthiness_certified: bool
    maintenance_hours: int
    manifest_verified: bool


def inspect_airframe(state: State) -> dict[str, Any]:
    """Perform a structural integrity and systems check."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "UNKNOWN")
    # Simulate an airworthiness certification process
    certified = inp.get("safety_inspection_passed", True)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_airframe:{tail}"],
        "tail_number": tail,
        "airworthiness_certified": certified,
    }


def verify_service_log(state: State) -> dict[str, Any]:
    """Review maintenance logs and total airframe hours."""
    inp = state.get("input") or {}
    hours = inp.get("current_hours", 0)
    # Check if hours are within safety limits and inspection passed
    safe_to_fly = state.get("airworthiness_certified", False) and hours < 20000
    return {
        "log": [f"{UNISPSC_CODE}:verify_service_log:hours={hours}"],
        "maintenance_hours": hours,
        "manifest_verified": safe_to_fly,
    }


def dispatch_aircraft(state: State) -> dict[str, Any]:
    """Finalize the flight state and emit authorization result."""
    is_ready = state.get("airworthiness_certified") and state.get("manifest_verified")
    tail = state.get("tail_number", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_aircraft:ready={is_ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "flight_status": "READY" if is_ready else "GROUNDED",
            "ok": is_ready,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_airframe)
_g.add_node("verify", verify_service_log)
_g.add_node("dispatch", dispatch_aircraft)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
