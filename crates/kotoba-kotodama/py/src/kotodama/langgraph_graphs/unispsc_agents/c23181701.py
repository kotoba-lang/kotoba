# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181701 — Tool (segment 23).
Bespoke logic for tool specification validation and maintenance scheduling.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181701"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Industrial Tools
    tool_type: str
    calibration_required: bool
    maintenance_interval_hours: int
    operational_status: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the tool metadata and determines its classification."""
    inp = state.get("input") or {}
    tool_type = inp.get("tool_type", "unspecified")
    needs_cal = inp.get("precision_grade", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "tool_type": tool_type,
        "calibration_required": needs_cal,
        "operational_status": "validated"
    }


def schedule_maintenance(state: State) -> dict[str, Any]:
    """Calculates maintenance cycles based on tool type and usage profile."""
    t_type = state.get("tool_type", "unspecified")

    # Logic: precision tools require shorter intervals
    interval = 500 if state.get("calibration_required") else 2000
    if t_type == "heavy_duty":
        interval = int(interval * 0.5)

    return {
        "log": [f"{UNISPSC_CODE}:schedule_maintenance"],
        "maintenance_interval_hours": interval,
        "operational_status": "scheduled"
    }


def emit_asset_record(state: State) -> dict[str, Any]:
    """Constructs the final digital twin record for the Tool actor."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "tool_type": state.get("tool_type"),
                "calibration_required": state.get("calibration_required"),
                "maintenance_interval": state.get("maintenance_interval_hours"),
                "status": "active"
            },
            "ok": True,
        },
        "operational_status": "ready"
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("schedule", schedule_maintenance)
_g.add_node("emit", emit_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "schedule")
_g.add_edge("schedule", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
