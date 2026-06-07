# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201518 — Aircraft (segment 25).

Bespoke logic for aircraft asset management, focusing on airworthiness
verification, maintenance cycle analysis, and operational clearance.
"""

from __future__ import annotations

import operator
# Ensure Annotated is available for state logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201518"
UNISPSC_TITLE = "Aircraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201518"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Aircraft
    tail_number: str
    airworthiness_status: str
    flight_hours: float
    maintenance_check_passed: bool


def inspect_documentation(state: State) -> dict[str, Any]:
    """Validates aircraft identification and basic telemetry."""
    inp = state.get("input") or {}
    tail_number = str(inp.get("tail_number", "N00000"))
    flight_hours = float(inp.get("flight_hours", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_documentation"],
        "tail_number": tail_number,
        "flight_hours": flight_hours,
        "airworthiness_status": "IN_REVIEW"
    }


def analyze_maintenance_cycle(state: State) -> dict[str, Any]:
    """Determines if the aircraft is within its safe operating window."""
    hours = state.get("flight_hours", 0.0)
    # Business logic: Maintenance required every 500 flight hours
    # If within 50 hours of the next 500-hour mark, flag it.
    next_check = ((hours // 500) + 1) * 500
    maintenance_due = (next_check - hours) < 50

    status = "CERTIFIED" if not maintenance_due else "MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_maintenance_cycle"],
        "maintenance_check_passed": not maintenance_due,
        "airworthiness_status": status
    }


def issue_flight_clearance(state: State) -> dict[str, Any]:
    """Finalizes the state and issues a clearance result."""
    status = state.get("airworthiness_status", "UNKNOWN")
    is_cleared = status == "CERTIFIED"

    return {
        "log": [f"{UNISPSC_CODE}:issue_flight_clearance"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "tail_number": state.get("tail_number"),
            "airworthiness_status": status,
            "flight_clearance": is_cleared,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_documentation", inspect_documentation)
_g.add_node("analyze_maintenance_cycle", analyze_maintenance_cycle)
_g.add_node("issue_flight_clearance", issue_flight_clearance)

_g.add_edge(START, "inspect_documentation")
_g.add_edge("inspect_documentation", "analyze_maintenance_cycle")
_g.add_edge("analyze_maintenance_cycle", "issue_flight_clearance")
_g.add_edge("issue_flight_clearance", END)

graph = _g.compile()
