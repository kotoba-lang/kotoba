# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181512"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Industrial Manufacturing Services (Anodizing)
    material_type: str
    coating_thickness_target: float
    actual_thickness: float
    quality_check_passed: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the industrial finishing specifications for the batch."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "6061 Aluminum Alloy"))
    target = float(inp.get("target_microns", 15.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs -> material: {material}, target: {target}um"],
        "material_type": material,
        "coating_thickness_target": target,
    }


def execute_anodizing(state: State) -> dict[str, Any]:
    """Simulates the electrolytic anodizing process and thickness accumulation."""
    target = state.get("coating_thickness_target", 15.0)
    # Simulate industrial process variance (±2%)
    actual = round(target * 1.015, 2)

    return {
        "log": [f"{UNISPSC_CODE}:execute_anodizing -> process complete, achieved {actual}um"],
        "actual_thickness": actual,
    }


def quality_inspection(state: State) -> dict[str, Any]:
    """Performs a simulated micro-thickness inspection and finalizes the agent output."""
    actual = state.get("actual_thickness", 0.0)
    target = state.get("coating_thickness_target", 15.0)

    # Tolerance for segment 23 industrial standards
    is_ok = abs(actual - target) < (target * 0.05)

    return {
        "log": [f"{UNISPSC_CODE}:quality_inspection -> result: {'PASS' if is_ok else 'FAIL'}"],
        "quality_check_passed": is_ok,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "details": {
                "material": state.get("material_type"),
                "measured_thickness": actual,
                "target_thickness": target
            }
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("process", execute_anodizing)
_g.add_node("inspect", quality_inspection)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
