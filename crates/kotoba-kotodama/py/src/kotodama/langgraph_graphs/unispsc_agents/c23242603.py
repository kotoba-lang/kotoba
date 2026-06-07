# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242603 — Machine.
Bespoke logic for industrial machinery management, diagnostic monitoring,
and operational lifecycle tracking within segment 23.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242603"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Machine-specific domain fields
    machine_id: str
    runtime_hours: float
    operating_status: str
    maintenance_alert: bool
    efficiency_index: float


def initialize_machine(state: State) -> dict[str, Any]:
    """Sets up the machine context from input data."""
    inp = state.get("input") or {}
    mid = inp.get("machine_id", "MCH-23-GENERIC")
    hours = float(inp.get("runtime_hours", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_machine:{mid}"],
        "machine_id": mid,
        "runtime_hours": hours,
        "operating_status": "STARTUP"
    }


def run_diagnostics(state: State) -> dict[str, Any]:
    """Analyzes runtime and calculates efficiency."""
    hours = state.get("runtime_hours", 0.0)
    # Threshold for maintenance alert is 5000 hours
    alert = hours > 5000.0
    # Simulated efficiency calculation
    efficiency = 0.98 if hours < 1000 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:run_diagnostics:alert={alert}"],
        "maintenance_alert": alert,
        "efficiency_index": efficiency,
        "operating_status": "DIAGNOSTIC"
    }


def execute_operation(state: State) -> dict[str, Any]:
    """Transitions to active or maintenance mode based on diagnostics."""
    alert = state.get("maintenance_alert", False)
    status = "MAINTENANCE_REQUIRED" if alert else "OPERATIONAL"

    return {
        "log": [f"{UNISPSC_CODE}:execute_operation:status={status}"],
        "operating_status": status
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Compiles the final result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_id": state.get("machine_id"),
            "operational_metrics": {
                "runtime": state.get("runtime_hours"),
                "efficiency": state.get("efficiency_index"),
                "status": state.get("operating_status")
            },
            "ok": not state.get("maintenance_alert", False),
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_machine)
_g.add_node("diagnose", run_diagnostics)
_g.add_node("operate", execute_operation)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "diagnose")
_g.add_edge("diagnose", "operate")
_g.add_edge("operate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
