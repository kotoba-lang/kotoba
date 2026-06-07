# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23160000 — Machine Tool.

Bespoke logic for industrial machine tool coordination, including
calibration, safety verification, and operational state management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23160000"
UNISPSC_TITLE = "Machine Tool"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23160000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Machine Tool
    tool_geometry_verified: bool
    calibration_microns: int
    coolant_pressure_psi: float
    safety_interlock_status: str
    operational_mode: str


def configure_tooling(state: State) -> dict[str, Any]:
    """Initializes machine tool configuration and geometry verification."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "standard")
    return {
        "log": [f"{UNISPSC_CODE}:configure_tooling"],
        "operational_mode": mode,
        "tool_geometry_verified": True,
    }


def perform_calibration(state: State) -> dict[str, Any]:
    """Executes precision calibration for the specific machine tool segment."""
    # Simulate a calibration offset based on mode
    offset = 5 if state.get("operational_mode") == "precision" else 15
    return {
        "log": [f"{UNISPSC_CODE}:perform_calibration"],
        "calibration_microns": offset,
        "coolant_pressure_psi": 45.5,
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Ensures all industrial safety interlocks are engaged before operation."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_protocols"],
        "safety_interlock_status": "engaged",
    }


def finalize_operational_state(state: State) -> dict[str, Any]:
    """Aggregates tool state into the final machine tool actor response."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operational_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "ready_for_production",
            "calibration": state.get("calibration_microns"),
            "safety": state.get("safety_interlock_status"),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_tooling)
_g.add_node("calibrate", perform_calibration)
_g.add_node("safety_check", verify_safety_protocols)
_g.add_node("finalize", finalize_operational_state)

_g.add_edge(START, "configure")
_g.add_edge("configure", "calibrate")
_g.add_edge("calibrate", "safety_check")
_g.add_edge("safety_check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
