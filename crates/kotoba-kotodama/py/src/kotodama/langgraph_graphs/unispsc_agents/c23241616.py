# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241616 — Tool (segment 23).

This bespoke agent manages the lifecycle of industrial tooling, including
specification validation, calibration state management, and safety auditing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241616"
UNISPSC_TITLE = "Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241616"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tool_metadata: dict[str, Any]
    calibration_status: str
    maintenance_interval: int
    safety_check_passed: bool


def initialize_tool(state: State) -> dict[str, Any]:
    """Extracts tool metadata and initializes maintenance parameters."""
    inp = state.get("input") or {}
    tool_data = inp.get("tool_data", {"type": "standard", "id": "unknown-000"})
    return {
        "log": [f"{UNISPSC_CODE}:initialize_tool"],
        "tool_metadata": tool_data,
        "maintenance_interval": inp.get("maintenance_interval", 500),
    }


def perform_calibration(state: State) -> dict[str, Any]:
    """Evaluates calibration requirements based on tool type."""
    metadata = state.get("tool_metadata", {})
    tool_type = metadata.get("type", "generic")

    # Precision tools require explicit calibration steps
    status = "calibrated" if tool_type != "precision" else "verification_required"

    return {
        "log": [f"{UNISPSC_CODE}:perform_calibration"],
        "calibration_status": status,
    }


def conduct_safety_audit(state: State) -> dict[str, Any]:
    """Performs a logic-based safety audit on the tool state."""
    metadata = state.get("tool_metadata", {})
    calibration = state.get("calibration_status", "unknown")

    # Tool is safe if it is calibrated and has a valid ID
    passed = calibration == "calibrated" and metadata.get("id") != "unknown-000"

    return {
        "log": [f"{UNISPSC_CODE}:conduct_safety_audit"],
        "safety_check_passed": passed,
    }


def emit_tool_state(state: State) -> dict[str, Any]:
    """Finalizes the tool record and emits the resulting state."""
    is_ok = state.get("safety_check_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_tool_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "summary": {
                "tool_id": state.get("tool_metadata", {}).get("id"),
                "calibration": state.get("calibration_status"),
                "safety_audit": "passed" if is_ok else "failed",
                "maintenance_window": state.get("maintenance_interval"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_tool", initialize_tool)
_g.add_node("perform_calibration", perform_calibration)
_g.add_node("conduct_safety_audit", conduct_safety_audit)
_g.add_node("emit_tool_state", emit_tool_state)

_g.add_edge(START, "initialize_tool")
_g.add_edge("initialize_tool", "perform_calibration")
_g.add_edge("perform_calibration", "conduct_safety_audit")
_g.add_edge("conduct_safety_audit", "emit_tool_state")
_g.add_edge("emit_tool_state", END)

graph = _g.compile()
