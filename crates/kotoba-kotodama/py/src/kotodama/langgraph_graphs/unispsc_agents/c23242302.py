# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242302 — Lathe (segment 23).

Bespoke graph logic for Lathe operations, managing machine configuration,
turning cycles, and quality control metrics.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242302"
UNISPSC_TITLE = "Lathe"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242302"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lathe
    spindle_speed_rpm: int
    tool_offset_mm: float
    material_type: str
    safety_check_passed: bool
    tool_wear_index: float


def configure_lathe(state: State) -> dict[str, Any]:
    """Validates machining parameters and prepares the spindle."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    target_rpm = inp.get("target_rpm", 1200)

    # Simple safety check: spindle speed within operating limits
    safety_pass = 0 < target_rpm <= 5000

    return {
        "log": [f"{UNISPSC_CODE}:configure_lathe"],
        "material_type": material,
        "spindle_speed_rpm": target_rpm,
        "safety_check_passed": safety_pass,
        "tool_offset_mm": 0.0,
    }


def execute_turning_cycle(state: State) -> dict[str, Any]:
    """Simulates the turning operation and calculates tool wear."""
    if not state.get("safety_check_passed", False):
        return {"log": [f"{UNISPSC_CODE}:turning_aborted_safety"]}

    # Calculate synthetic tool wear based on RPM and material
    base_wear = 0.005
    material_multiplier = 1.5 if state.get("material_type") == "stainless_steel" else 1.0
    calculated_wear = base_wear * (state.get("spindle_speed_rpm", 1000) / 1000) * material_multiplier

    return {
        "log": [f"{UNISPSC_CODE}:execute_turning_cycle"],
        "tool_wear_index": calculated_wear,
        "tool_offset_mm": 0.025,  # Nominal thermal expansion
    }


def finalize_inspection(state: State) -> dict[str, Any]:
    """Performs post-process quality check and emits the result."""
    ok = state.get("safety_check_passed", False) and state.get("tool_wear_index", 1.0) < 0.1

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inspection"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "completed" if ok else "failed",
            "metrics": {
                "final_wear": state.get("tool_wear_index"),
                "thermal_offset": state.get("tool_offset_mm")
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_lathe)
_g.add_node("machine", execute_turning_cycle)
_g.add_node("inspect", finalize_inspection)

_g.add_edge(START, "configure")
_g.add_edge("configure", "machine")
_g.add_edge("machine", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
