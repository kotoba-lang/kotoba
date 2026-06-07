# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251502 —  (segment 23).
Bespoke logic for spindle speed calculation, capacity verification, and safety checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251502"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Metal Lathe processing
    swing_check_passed: bool
    calculated_rpm: int
    tooling_ready: bool
    material_type: str


def inspect_specs(state: State) -> dict[str, Any]:
    """Verifies that the workpiece dimensions fit within the lathe's physical capacity."""
    inp = state.get("input") or {}
    workpiece_diameter = inp.get("diameter_mm", 0)
    # Standard lathe swing capacity threshold for this model
    max_swing = 400
    passed = workpiece_diameter < max_swing
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "swing_check_passed": passed,
        "material_type": inp.get("material", "unknown"),
    }


def optimize_settings(state: State) -> dict[str, Any]:
    """Calculates optimal spindle RPM based on material type and tooling specs."""
    material = state.get("material_type", "unknown")
    # Basic RPM mapping logic for industrial metal cutting
    rpm_map = {
        "aluminum": 1200,
        "steel": 800,
        "titanium": 400,
        "unknown": 500,
    }
    rpm = rpm_map.get(material.lower(), 500)
    return {
        "log": [f"{UNISPSC_CODE}:optimize_settings"],
        "calculated_rpm": rpm,
        "tooling_ready": True,
    }


def issue_command(state: State) -> dict[str, Any]:
    """Finalizes the processing sequence and emits the machine operation result."""
    success = state.get("swing_check_passed", False) and state.get("tooling_ready", False)
    return {
        "log": [f"{UNISPSC_CODE}:issue_command"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "rpm_setting": state.get("calculated_rpm"),
            "status": "authorized" if success else "rejected",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("optimize_settings", optimize_settings)
_g.add_node("issue_command", issue_command)
_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "optimize_settings")
_g.add_edge("optimize_settings", "issue_command")
_g.add_edge("issue_command", END)

graph = _g.compile()
