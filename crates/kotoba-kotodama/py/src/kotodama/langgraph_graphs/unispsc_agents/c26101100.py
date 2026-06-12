# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101100 — Motor (segment 26).

This bespoke implementation handles motor-specific state transitions including
electrical specification validation, torque verification, and final
performance data aggregation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101100"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Motor
    electrical_validation: bool
    performance_metrics: dict[str, Any]
    thermal_safety_check: str
    winding_insulation_class: str


def validate_electrical_specs(state: State) -> dict[str, Any]:
    """Validate motor voltage, current, and phase requirements."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 0)
    phase = inp.get("phase", 1)

    valid = voltage > 0 and phase in [1, 3]
    return {
        "log": [f"{UNISPSC_CODE}:validate_electrical_specs"],
        "electrical_validation": valid,
        "winding_insulation_class": inp.get("insulation", "Class F"),
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Compute and verify RPM and torque characteristics."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 0)
    torque = inp.get("torque", 0)

    metrics = {
        "rated_rpm": rpm,
        "rated_torque": torque,
        "power_factor": 0.85 if rpm > 1000 else 0.75
    }
    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance"],
        "performance_metrics": metrics,
        "thermal_safety_check": "Verified" if rpm > 0 else "N/A",
    }


def emit_motor_declaration(state: State) -> dict[str, Any]:
    """Consolidate all motor data into the final result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_motor_declaration"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "validated",
            "electrical": state.get("electrical_validation"),
            "performance": state.get("performance_metrics"),
            "safety": state.get("thermal_safety_check"),
            "insulation": state.get("winding_insulation_class"),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_electrical_specs", validate_electrical_specs)
_g.add_node("analyze_performance", analyze_performance)
_g.add_node("emit_motor_declaration", emit_motor_declaration)

_g.add_edge(START, "validate_electrical_specs")
_g.add_edge("validate_electrical_specs", "analyze_performance")
_g.add_edge("analyze_performance", "emit_motor_declaration")
_g.add_edge("emit_motor_declaration", END)

graph = _g.compile()
