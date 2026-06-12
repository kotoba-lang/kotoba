# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242501 — Machine (segment 23).

Bespoke graph logic for industrial machinery management, telemetry ingestion,
and diagnostic status tracking.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242501"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for "Machine"
    machine_serial: str
    operating_status: str
    runtime_hours: float
    safety_check_passed: bool


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Ingests raw machine telemetry and initializes state."""
    inp = state.get("input") or {}
    serial = str(inp.get("serial", "SN-000"))
    hours = float(inp.get("hours", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry:serial={serial}"],
        "machine_serial": serial,
        "runtime_hours": hours,
        "operating_status": "standby",
    }


def run_diagnostics(state: State) -> dict[str, Any]:
    """Performs safety and maintenance diagnostics on the machine."""
    hours = state.get("runtime_hours", 0.0)
    # Machines require service after 10,000 hours
    needs_maintenance = hours > 10000.0
    safety_ok = hours < 25000.0  # Critical threshold

    status = "active" if safety_ok else "emergency_stop"
    if needs_maintenance:
        status = "maintenance_required"

    return {
        "log": [f"{UNISPSC_CODE}:run_diagnostics:status={status}"],
        "operating_status": status,
        "safety_check_passed": safety_ok,
    }


def report_machine_state(state: State) -> dict[str, Any]:
    """Generates the final state report for the actor."""
    status = state.get("operating_status")
    serial = state.get("machine_serial")

    return {
        "log": [f"{UNISPSC_CODE}:report_machine_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_report": {
                "serial": serial,
                "status": status,
                "safety_cleared": state.get("safety_check_passed"),
                "total_hours": state.get("runtime_hours"),
            },
            "ok": state.get("safety_check_passed", False),
        },
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_telemetry)
_g.add_node("diagnose", run_diagnostics)
_g.add_node("report", report_machine_state)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "diagnose")
_g.add_edge("diagnose", "report")
_g.add_edge("report", END)

graph = _g.compile()
