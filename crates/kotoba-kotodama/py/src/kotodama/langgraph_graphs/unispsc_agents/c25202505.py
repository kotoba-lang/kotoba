# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202505 — Aircraft System (segment 25).

Bespoke logic for aircraft system lifecycle management, including pre-flight
inspection, systems integration, and flight clearance verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202505"
UNISPSC_TITLE = "Aircraft System"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Aircraft System
    avionics_check_passed: bool
    fuel_system_status: str
    maintenance_log_id: str
    flight_ready: bool


def preflight_inspection(state: State) -> dict[str, Any]:
    """Inspects basic system health and avionics status from input."""
    inp = state.get("input") or {}
    log_entry = f"{UNISPSC_CODE}:preflight_inspection"
    maintenance_id = inp.get("maintenance_id", "M-UNKNOWN")

    return {
        "log": [log_entry],
        "maintenance_log_id": maintenance_id,
        "avionics_check_passed": bool(inp.get("avionics_ok")),
    }


def systems_integration(state: State) -> dict[str, Any]:
    """Processes fuel levels and determines operational status."""
    log_entry = f"{UNISPSC_CODE}:systems_integration"
    fuel_level = state.get("input", {}).get("fuel_level", 0)

    if fuel_level > 80:
        status = "OPTIMAL"
    elif fuel_level > 20:
        status = "CAUTION"
    else:
        status = "CRITICAL"

    return {
        "log": [log_entry],
        "fuel_system_status": status,
    }


def flight_clearance(state: State) -> dict[str, Any]:
    """Final check to determine if the aircraft system is flight ready."""
    log_entry = f"{UNISPSC_CODE}:flight_clearance"

    avionics_ok = state.get("avionics_check_passed", False)
    fuel_status = state.get("fuel_system_status", "CRITICAL")
    ready = avionics_ok and fuel_status != "CRITICAL"

    return {
        "log": [log_entry],
        "flight_ready": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "flight_ready": ready,
            "maintenance_id": state.get("maintenance_log_id"),
            "fuel_status": fuel_status,
        },
    }


_g = StateGraph(State)
_g.add_node("preflight_inspection", preflight_inspection)
_g.add_node("systems_integration", systems_integration)
_g.add_node("flight_clearance", flight_clearance)

_g.add_edge(START, "preflight_inspection")
_g.add_edge("preflight_inspection", "systems_integration")
_g.add_edge("systems_integration", "flight_clearance")
_g.add_edge("flight_clearance", END)

graph = _g.compile()
