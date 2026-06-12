# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171712 — Brake (segment 25).
Bespoke implementation for monitoring and validating brake component specifications.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171712"
UNISPSC_TITLE = "Brake"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171712"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Brake components
    brake_type: str
    pad_thickness_mm: float
    inspection_passed: bool
    thermal_rating: str


def validate_input(state: State) -> dict[str, Any]:
    """Validates the input specification for the brake component."""
    inp = state.get("input") or {}
    b_type = inp.get("type", "disc")
    thickness = float(inp.get("thickness", 12.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_input: type={b_type}"],
        "brake_type": b_type,
        "pad_thickness_mm": thickness,
    }


def perform_safety_check(state: State) -> dict[str, Any]:
    """Analyzes brake pad thickness against safety thresholds."""
    thickness = state.get("pad_thickness_mm", 0.0)
    # Minimum safety thickness is typically 3.0mm
    passed = thickness >= 3.0
    rating = "High" if thickness > 10.0 else "Standard"
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_check: passed={passed}"],
        "inspection_passed": passed,
        "thermal_rating": rating,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Generates the final inspection report and telemetry data."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "PASS" if state.get("inspection_passed") else "FAIL",
            "telemetry": {
                "brake_type": state.get("brake_type"),
                "thickness": state.get("pad_thickness_mm"),
                "thermal_rating": state.get("thermal_rating"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_input)
_g.add_node("check", perform_safety_check)
_g.add_node("emit", finalize_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "check")
_g.add_edge("check", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
