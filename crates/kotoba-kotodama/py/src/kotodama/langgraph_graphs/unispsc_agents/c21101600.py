# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101600 — Machine (segment 21).

Bespoke LangGraph implementation for agricultural and forestry machinery logic.
This agent handles machine diagnostics, operational configuration, and
safety status reporting for harvesting and post-harvesting equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101600"
UNISPSC_TITLE = "Machine"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    machine_id: str
    operational_status: str
    maintenance_due: bool
    safety_clearance: bool
    calibration_offset: float


def validate_vitals(state: State) -> dict[str, Any]:
    """Node to verify safety systems and machine identity."""
    inp = state.get("input") or {}
    machine_id = inp.get("machine_id", "M-UNKNOWN")

    # Check if safety interlocks are bypassed in input
    safety_ready = inp.get("safety_bypass") is not True

    return {
        "log": [f"{UNISPSC_CODE}:validate_vitals"],
        "machine_id": machine_id,
        "safety_clearance": safety_ready,
        "operational_status": "ready" if safety_ready else "safety_locked"
    }


def configure_operation(state: State) -> dict[str, Any]:
    """Node to calculate calibration and maintenance state."""
    inp = state.get("input") or {}
    hours = inp.get("operating_hours", 0)

    # Machines in segment 21 require maintenance every 500 hours
    maint_due = hours >= 500

    return {
        "log": [f"{UNISPSC_CODE}:configure_operation"],
        "maintenance_due": maint_due,
        "calibration_offset": 0.05 if maint_due else 0.01,
        "operational_status": "maintenance_warning" if maint_due else state.get("operational_status")
    }


def emit_status(state: State) -> dict[str, Any]:
    """Final node to produce the compliance and status report."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machine_id": state.get("machine_id"),
            "system_ok": state.get("safety_clearance") and state.get("operational_status") != "safety_locked",
            "maintenance_required": state.get("maintenance_due"),
            "precision_tolerance": state.get("calibration_offset"),
            "segment": UNISPSC_SEGMENT,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_vitals", validate_vitals)
_g.add_node("configure_operation", configure_operation)
_g.add_node("emit_status", emit_status)

_g.add_edge(START, "validate_vitals")
_g.add_edge("validate_vitals", "configure_operation")
_g.add_edge("configure_operation", "emit_status")
_g.add_edge("emit_status", END)

graph = _g.compile()
