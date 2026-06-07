# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242107 — Tool (segment 23).

Bespoke logic for Tool lifecycle management, focusing on inspection,
calibration, and metadata emission within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242107"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242107"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tool_type: str
    maintenance_status: str
    calibration_offset: float
    inspection_passed: bool


def inspect_tool(state: State) -> dict[str, Any]:
    """Validates the physical integrity of the tool based on input data."""
    inp = state.get("input") or {}
    t_type = inp.get("type", "standard")
    # Tools with high usage count are flagged during inspection
    passed = inp.get("usage_count", 0) < 5000

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tool"],
        "tool_type": t_type,
        "inspection_passed": passed,
    }


def calibrate_tool(state: State) -> dict[str, Any]:
    """Calculates calibration offsets and updates maintenance status."""
    t_type = state.get("tool_type", "standard")
    is_passed = state.get("inspection_passed", False)

    # Precision tools require a specific offset adjustment
    offset = 0.015 if t_type == "precision" else 0.0
    status = "ready" if is_passed else "flagged_for_repair"

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_tool"],
        "calibration_offset": offset,
        "maintenance_status": status,
    }


def emit_tool_record(state: State) -> dict[str, Any]:
    """Finalizes the tool state and produces the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_tool_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "tool_type": state.get("tool_type"),
                "status": state.get("maintenance_status"),
                "offset": state.get("calibration_offset"),
            },
            "ok": state.get("inspection_passed", False),
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_tool)
_g.add_node("calibrate", calibrate_tool)
_g.add_node("emit", emit_tool_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
