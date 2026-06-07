# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242101 — Horizontal boring machines (segment 23).

Bespoke graph for industrial manufacturing machinery management. This agent
handles specification validation, machining cycle configuration, and
operational status reporting for horizontal boring equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242101"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state fields for horizontal boring machines
    spindle_speed_rpm: int
    table_load_kg: float
    coolant_active: bool
    calibration_status: str
    safety_check_passed: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates machining parameters and machine safety status."""
    inp = state.get("input") or {}
    spindle = inp.get("spindle_speed", 0)
    load = inp.get("load_weight", 0.0)

    # Simple logic: spindle speed limit 3000 RPM, load limit 5000kg
    is_safe = 0 < spindle <= 3000 and load <= 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "spindle_speed_rpm": spindle,
        "table_load_kg": float(load),
        "safety_check_passed": is_safe,
        "calibration_status": "verified" if is_safe else "pending_review"
    }


def configure_cycle(state: State) -> dict[str, Any]:
    """Configures the boring cycle based on validated specifications."""
    is_safe = state.get("safety_check_passed", False)

    if not is_safe:
        return {
            "log": [f"{UNISPSC_CODE}:configure_cycle_aborted"],
            "coolant_active": False
        }

    return {
        "log": [f"{UNISPSC_CODE}:configure_cycle_ready"],
        "coolant_active": True
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final operational report for the machinery."""
    is_safe = state.get("safety_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ready" if is_safe else "error",
            "telemetry": {
                "spindle_rpm": state.get("spindle_speed_rpm"),
                "load": state.get("table_load_kg"),
                "coolant": state.get("coolant_active")
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("configure", configure_cycle)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
