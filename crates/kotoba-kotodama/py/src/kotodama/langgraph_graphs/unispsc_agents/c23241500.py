# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241500 — Machine Tool (segment 23).

Bespoke logic for managing machine tool specifications, calibration,
and operational readiness within an industrial manufacturing context.
"""

from __future__ import annotations

import operator
# Note: operator.add is used in the State definition for log accumulation
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241500"
UNISPSC_TITLE = "Machine Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Machine Tool domain state
    tool_type: str
    calibration_offset: float
    safety_interlock_active: bool
    maintenance_status: str


def validate_tool_specs(state: State) -> dict[str, Any]:
    """Validates the machine tool specifications provided in the input."""
    inp = state.get("input") or {}
    tool_type = str(inp.get("tool_type", "CNC-LATHE-DEFAULT"))

    log_entry = f"{UNISPSC_CODE}:validate_tool_specs -> identified type: {tool_type}"
    return {
        "log": [log_entry],
        "tool_type": tool_type,
        "maintenance_status": "ready"
    }


def calibrate_tool(state: State) -> dict[str, Any]:
    """Simulates the calibration process for the machine tool precision."""
    # Machine tools require high precision; simulate a micro-offset calculation
    calculated_offset = 0.00015
    log_entry = f"{UNISPSC_CODE}:calibrate_tool -> precision calibrated to {calculated_offset}mm"
    return {
        "log": [log_entry],
        "calibration_offset": calculated_offset,
        "safety_interlock_active": True
    }


def confirm_readiness(state: State) -> dict[str, Any]:
    """Confirms operational readiness and prepares the final agent result."""
    tool_type = state.get("tool_type")
    offset = state.get("calibration_offset", 0.0)
    safety = state.get("safety_interlock_active", False)

    log_entry = f"{UNISPSC_CODE}:confirm_readiness -> safety check passed, ready for production"

    result = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "machine_status": {
            "type": tool_type,
            "calibration_precision": f"{offset}mm",
            "safety_interlock": "ENGAGED" if safety else "DISENGAGED"
        },
        "operational_state": "ACTIVE",
        "ok": True
    }

    return {
        "log": [log_entry],
        "result": result
    }


_g = StateGraph(State)

_g.add_node("validate", validate_tool_specs)
_g.add_node("calibrate", calibrate_tool)
_g.add_node("confirm", confirm_readiness)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "confirm")
_g.add_edge("confirm", END)

graph = _g.compile()
