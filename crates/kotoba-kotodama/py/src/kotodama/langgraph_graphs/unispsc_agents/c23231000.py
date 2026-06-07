# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231000 — Lathe.

This bespoke graph manages state transitions for a lathe machining process,
simulating setup, operation, and quality assurance for industrial parts.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231000"
UNISPSC_TITLE = "Lathe"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lathe
    workpiece_material: str
    spindle_speed_rpm: int
    tooling_profile: str
    tolerance_verified: bool
    safety_interlock: bool


def configure_setup(state: State) -> dict[str, Any]:
    """Initializes machine parameters based on the workpiece specifications."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    speed = 1200 if material == "aluminum" else 800

    return {
        "log": [f"{UNISPSC_CODE}:configure_setup - Material: {material}"],
        "workpiece_material": material,
        "spindle_speed_rpm": speed,
        "tooling_profile": inp.get("tool", "carbide_turning_v1"),
        "safety_interlock": True,
    }


def execute_machining(state: State) -> dict[str, Any]:
    """Simulates the turning/cutting process on the lathe."""
    speed = state.get("spindle_speed_rpm", 0)
    material = state.get("workpiece_material", "unknown")

    # Simulate processing time or complexity check
    status = "nominal" if state.get("safety_interlock") else "unsafe"

    return {
        "log": [f"{UNISPSC_CODE}:execute_machining - Speed {speed} RPM, Status {status}"],
        "tolerance_verified": status == "nominal"
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Finalizes the process and generates the digital twin result."""
    ok = state.get("tolerance_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance - Passed: {ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "machining_completed": ok,
            "material_processed": state.get("workpiece_material"),
            "final_metrics": {
                "spindle_avg_rpm": state.get("spindle_speed_rpm"),
                "tool_used": state.get("tooling_profile")
            }
        },
    }


_g = StateGraph(State)

_g.add_node("configure_setup", configure_setup)
_g.add_node("execute_machining", execute_machining)
_g.add_node("quality_assurance", quality_assurance)

_g.add_edge(START, "configure_setup")
_g.add_edge("configure_setup", "execute_machining")
_g.add_edge("execute_machining", "quality_assurance")
_g.add_edge("quality_assurance", END)

graph = _g.compile()
