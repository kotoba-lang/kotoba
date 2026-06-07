# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101503 — Vehicle (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101503"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vin: str
    odometer: int
    maintenance_status: str
    emissions_level: str
    owner_verified: bool


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Nodes that parses raw input for vehicle identification and current usage."""
    inp = state.get("input") or {}
    vin = inp.get("vin", "UNKNOWN")
    miles = inp.get("odometer", 0)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle_{vin}"],
        "vin": vin,
        "odometer": miles,
        "owner_verified": "owner_id" in inp,
    }


def assess_condition(state: State) -> dict[str, Any]:
    """Determines maintenance requirements based on vehicle telemetry."""
    odometer = state.get("odometer", 0)
    if odometer > 100000:
        status = "MAJOR_SERVICE_REQUIRED"
    elif odometer > 30000:
        status = "ROUTINE_MAINTENANCE"
    else:
        status = "OPTIMAL"

    return {
        "log": [f"{UNISPSC_CODE}:assess_condition_{status}"],
        "maintenance_status": status,
        "emissions_level": "Tier-4" if odometer < 50000 else "Tier-3",
    }


def certify_registration(state: State) -> dict[str, Any]:
    """Finalizes the vehicle record and prepares the actor response."""
    vin = state.get("vin", "UNKNOWN")
    is_ready = state.get("owner_verified", False) and state.get("maintenance_status") != "MAJOR_SERVICE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_registration"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "vin": vin,
            "status": state.get("maintenance_status"),
            "emissions": state.get("emissions_level"),
            "certified": is_ready,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_vehicle)
_g.add_node("assess", assess_condition)
_g.add_node("certify", certify_registration)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "assess")
_g.add_edge("assess", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
