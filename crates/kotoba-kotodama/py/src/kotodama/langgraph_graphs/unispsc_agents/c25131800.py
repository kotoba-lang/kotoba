# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131800 — Aircraft (segment 25).

Bespoke agent implementation for aircraft lifecycle management, including
pre-flight inspection, maintenance verification, and flight readiness certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131800"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft
    tail_number: str
    airworthiness_cert: bool
    flight_hours: int
    maintenance_status: str
    fuel_capacity_kg: float


def inspect_airframe(state: State) -> dict[str, Any]:
    """Node: Initial structural and electronic systems inspection."""
    inp = state.get("input") or {}
    tail = inp.get("tail_number", "UNKNOWN-00")
    hours = inp.get("flight_hours", 0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_airframe tail={tail}"],
        "tail_number": tail,
        "flight_hours": hours,
        "maintenance_status": "IN_PROGRESS"
    }


def verify_maintenance_logs(state: State) -> dict[str, Any]:
    """Node: Cross-reference flight hours with maintenance schedule."""
    hours = state.get("flight_hours", 0)
    # Simple rule: maintenance required every 500 hours
    is_certified = (hours % 500) < 450
    status = "VERIFIED" if is_certified else "MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_maintenance_logs cert={is_certified}"],
        "airworthiness_cert": is_certified,
        "maintenance_status": status
    }


def certify_readiness(state: State) -> dict[str, Any]:
    """Node: Final dispatch certification for the aircraft asset."""
    is_certified = state.get("airworthiness_cert", False)
    tail = state.get("tail_number", "N/A")
    status = state.get("maintenance_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:certify_readiness status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "asset_id": tail,
            "flight_ready": is_certified,
            "did": UNISPSC_DID,
            "status": "READY_FOR_FLIGHT" if is_certified else "GROUNDED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_airframe)
_g.add_node("verify", verify_maintenance_logs)
_g.add_node("certify", certify_readiness)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
