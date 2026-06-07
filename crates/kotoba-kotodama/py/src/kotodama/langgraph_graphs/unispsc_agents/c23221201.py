# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23221201 — Machine (segment 23).

This module implements bespoke logic for tracking and reporting machine
telemetry and operational status within the Etz Hayyim UNISPSC mesh.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23221201"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23221201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for "Machine"
    serial_number: str
    runtime_hours: float
    maintenance_status: str
    safety_protocol_active: bool


def validate_machine_telemetry(state: State) -> dict[str, Any]:
    """Ingests and validates incoming machine telemetry data."""
    inp = state.get("input") or {}
    sn = str(inp.get("serial_number", "SN-UNKNOWN"))
    hours = float(inp.get("runtime_hours", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_machine_telemetry"],
        "serial_number": sn,
        "runtime_hours": hours,
        "safety_protocol_active": inp.get("safety_active", True),
    }


def analyze_operational_health(state: State) -> dict[str, Any]:
    """Analyzes machine state to determine maintenance requirements."""
    hours = state.get("runtime_hours", 0.0)

    if hours > 10000:
        status = "CRITICAL_OVERHAUL_REQUIRED"
    elif hours > 5000:
        status = "PREVENTATIVE_MAINTENANCE_DUE"
    else:
        status = "OPERATIONAL_OPTIMAL"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_operational_health"],
        "maintenance_status": status,
    }


def generate_status_report(state: State) -> dict[str, Any]:
    """Constructs the final machine status payload."""
    status = state.get("maintenance_status", "UNKNOWN")
    safety = state.get("safety_protocol_active", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_status_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "serial": state.get("serial_number"),
                "hours": state.get("runtime_hours"),
                "status": status,
                "safety_ok": safety
            },
            "ok": status != "CRITICAL_OVERHAUL_REQUIRED" and safety
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_machine_telemetry)
_g.add_node("analyze", analyze_operational_health)
_g.add_node("report", generate_status_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "report")
_g.add_edge("report", END)

graph = _g.compile()
