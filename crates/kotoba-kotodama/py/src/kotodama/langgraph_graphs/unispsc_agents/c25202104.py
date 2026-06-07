# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202104 — Aircraft (segment 25).

Bespoke logic for aircraft inventory and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202104"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    registration_id: str
    maintenance_status: str
    flight_hours: float
    safety_certified: bool


def inspect_aircraft(state: State) -> dict[str, Any]:
    """Extracts aircraft metadata from the input payload."""
    inp = state.get("input") or {}
    reg = inp.get("registration_id", "UNKNOWN-AV-000")
    hours = float(inp.get("flight_hours", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_aircraft:identified_{reg}"],
        "registration_id": reg,
        "flight_hours": hours,
    }


def verify_maintenance(state: State) -> dict[str, Any]:
    """Performs a safety check based on flight hours and service history."""
    hours = state.get("flight_hours", 0.0)
    # Simple logic: aircraft with more than 5000 flight hours require mandatory overhaul
    status = "OPERATIONAL" if hours < 5000 else "MAINTENANCE_REQUIRED"
    certified = status == "OPERATIONAL"
    return {
        "log": [f"{UNISPSC_CODE}:verify_maintenance:status_{status}"],
        "maintenance_status": status,
        "safety_certified": certified,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Compiles the final validation result for the aircraft entity."""
    certified = state.get("safety_certified", False)
    status = state.get("maintenance_status", "UNKNOWN")
    reg = state.get("registration_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record:complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "registration": reg,
            "maintenance_status": status,
            "certified": certified,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_aircraft", inspect_aircraft)
_g.add_node("verify_maintenance", verify_maintenance)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "inspect_aircraft")
_g.add_edge("inspect_aircraft", "verify_maintenance")
_g.add_edge("verify_maintenance", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
