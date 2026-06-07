# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131700 — Aircraft (segment 25).

Bespoke graph logic for aircraft procurement and lifecycle management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131700"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft
    tail_number: str
    airworthiness_status: str
    maintenance_log_id: str
    flight_ready: bool


def inspect_aircraft(state: State) -> dict[str, Any]:
    """Verify physical and documentation status of the aircraft."""
    inp = state.get("input") or {}
    tail_number = inp.get("tail_number", "N/A")
    log_id = inp.get("maintenance_log_id", "LOG-000")

    # Logic to simulate airworthiness inspection
    passed = inp.get("inspection_passed", True)
    status = "CERTIFIED" if passed else "GROUNDED"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_aircraft tail={tail_number} status={status}"],
        "tail_number": tail_number,
        "maintenance_log_id": log_id,
        "airworthiness_status": status,
    }


def certify_flight(state: State) -> dict[str, Any]:
    """Confirm regulatory and safety compliance for flight operations."""
    status = state.get("airworthiness_status")
    is_ready = status == "CERTIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_flight ready={is_ready}"],
        "flight_ready": is_ready,
    }


def dispatch(state: State) -> dict[str, Any]:
    """Finalize the aircraft record and emit the procurement/status result."""
    tail = state.get("tail_number", "N/A")
    ready = state.get("flight_ready", False)

    return {
        "log": [f"{UNISPSC_CODE}:dispatch tail={tail} final_ready={ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tail_number": tail,
            "flight_ready": ready,
            "operation_status": "DISPATCHED" if ready else "HELD",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_aircraft)
_g.add_node("certify", certify_flight)
_g.add_node("dispatch", dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "certify")
_g.add_edge("certify", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
