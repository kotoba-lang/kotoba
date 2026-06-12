# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231903 — Machine (segment 23).

Bespoke graph logic for industrial machinery assets. This agent handles
machine identification, safety lockout verification based on operational
telemetry, and maintenance status reporting for segment 23 equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231903"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    machine_id: str
    safety_lockout: bool
    maintenance_status: str
    operational_hours: int


def validate_asset(state: State) -> dict[str, Any]:
    """Extracts and validates the machine identifier from the input context."""
    inp = state.get("input") or {}
    machine_id = inp.get("machine_id", "ASSET-GENERIC-2323")
    return {
        "log": [f"{UNISPSC_CODE}:validate_asset:id={machine_id}"],
        "machine_id": machine_id,
        "operational_hours": inp.get("operational_hours", 0),
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Checks operational hours against safety thresholds to determine lockout status."""
    hours = state.get("operational_hours", 0)
    # Threshold: machines exceeding 8000 hours require mandatory inspection lockout
    lockout_active = hours > 8000
    status = "MAINTENANCE_DUE" if lockout_active else "OPERATIONAL"

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_protocols:lockout={lockout_active}"],
        "safety_lockout": lockout_active,
        "maintenance_status": status,
    }


def generate_status_report(state: State) -> dict[str, Any]:
    """Compiles the final machine state report for the Unispsc registry."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_status_report"],
        "result": {
            "machine_id": state.get("machine_id"),
            "safety_clearance": not state.get("safety_lockout", False),
            "status": state.get("maintenance_status"),
            "telemetry_summary": {
                "hours": state.get("operational_hours"),
                "unispsc_metadata": {
                    "code": UNISPSC_CODE,
                    "title": UNISPSC_TITLE,
                    "did": UNISPSC_DID,
                }
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_asset", validate_asset)
_g.add_node("verify_safety", verify_safety_protocols)
_g.add_node("generate_report", generate_status_report)

_g.add_edge(START, "validate_asset")
_g.add_edge("validate_asset", "verify_safety")
_g.add_edge("verify_safety", "generate_report")
_g.add_edge("generate_report", END)

graph = _g.compile()
