# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25132005 — Aircraft (segment 25).
Bespoke logic for aircraft registration and airworthiness verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25132005"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25132005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Aircraft
    tail_number: str
    airworthiness_status: str
    maintenance_logs_verified: bool
    flight_hours: int


def inspect_aircraft(state: State) -> dict[str, Any]:
    """Node to parse input and initiate inspection of the aircraft asset."""
    inp = state.get("input") or {}
    tail_number = inp.get("tail_number", "N-PENDING")
    flight_hours = inp.get("flight_hours", 0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_aircraft tail_number={tail_number}"],
        "tail_number": tail_number,
        "flight_hours": flight_hours,
        "maintenance_logs_verified": False
    }


def verify_airworthiness(state: State) -> dict[str, Any]:
    """Node to verify maintenance logs and determine airworthiness status."""
    flight_hours = state.get("flight_hours", 0)

    # Simulation logic for airworthiness certification
    logs_ok = flight_hours >= 0
    status = "CERTIFIED" if logs_ok else "GROUNDED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_airworthiness status={status}"],
        "maintenance_logs_verified": logs_ok,
        "airworthiness_status": status
    }


def register_aircraft(state: State) -> dict[str, Any]:
    """Node to finalize registration in the actor system and emit result."""
    tail_number = state.get("tail_number")
    status = state.get("airworthiness_status")

    return {
        "log": [f"{UNISPSC_CODE}:register_aircraft"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "asset_data": {
                "tail_number": tail_number,
                "airworthiness": status,
                "verified": state.get("maintenance_logs_verified"),
                "total_hours": state.get("flight_hours")
            },
            "ok": status == "CERTIFIED"
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_aircraft)
_g.add_node("verify", verify_airworthiness)
_g.add_node("register", register_aircraft)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "register")
_g.add_edge("register", END)

graph = _g.compile()
