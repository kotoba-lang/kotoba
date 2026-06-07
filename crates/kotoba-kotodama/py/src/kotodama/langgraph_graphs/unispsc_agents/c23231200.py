# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231200 — Machine (segment 23).

Bespoke graph logic for industrial machinery tracking and lifecycle management.
This agent handles machine registration, maintenance cycle validation, and
operational dispatch logging within the Etz Hayyim UNISPSC ecosystem.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231200"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific machine state fields
    unit_serial: str
    operational_hours: float
    maintenance_status: str
    safety_certified: bool


def register_unit(state: State) -> dict[str, Any]:
    """Extracts machine identification and initial telemetry from input."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SN-UNKNOWN")
    hours = float(inp.get("hours", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:register_unit:{serial}"],
        "unit_serial": serial,
        "operational_hours": hours,
    }


def validate_maintenance_cycle(state: State) -> dict[str, Any]:
    """Checks if the machine is within safe operating parameters."""
    hours = state.get("operational_hours", 0.0)
    # Logic: Machines requiring service every 500 hours
    needs_service = hours >= 500.0
    status = "MAINTENANCE_REQUIRED" if needs_service else "OPERATIONAL"

    return {
        "log": [f"{UNISPSC_CODE}:validate_maintenance:{status}"],
        "maintenance_status": status,
        "safety_certified": not needs_service,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Compiles the final machine status report for the ledger."""
    is_safe = state.get("safety_certified", False)
    serial = state.get("unit_serial", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "serial_number": serial,
            "dispatch_ready": is_safe,
            "status": state.get("maintenance_status", "UNKNOWN"),
        },
    }


_g = StateGraph(State)

_g.add_node("register_unit", register_unit)
_g.add_node("validate_maintenance_cycle", validate_maintenance_cycle)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "register_unit")
_g.add_edge("register_unit", "validate_maintenance_cycle")
_g.add_edge("validate_maintenance_cycle", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
