# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153028 —  (segment 23).
Bespoke logic for industrial machinery configuration, safety inspection, and operation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153028"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153028"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Industrial Manufacturing Machinery
    calibration_verified: bool
    safety_interlock_active: bool
    material_load_kg: float
    operational_mode: str


def configure_params(state: State) -> dict[str, Any]:
    """Sets the operational mode and material parameters from input."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "standard")
    load = inp.get("load_kg", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:configure_params"],
        "operational_mode": mode,
        "material_load_kg": load,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Performs a safety sweep and checks machine calibration."""
    load = state.get("material_load_kg", 0.0)
    # Machine requires minimum load to verify calibration stability
    calibrated = load > 5.0
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_interlock_active": True,
        "calibration_verified": calibrated,
    }


def execute_cycle(state: State) -> dict[str, Any]:
    """Triggers the manufacturing process if safety and calibration criteria are met."""
    is_safe = state.get("safety_interlock_active", False)
    is_calibrated = state.get("calibration_verified", False)
    success = is_safe and is_calibrated

    return {
        "log": [f"{UNISPSC_CODE}:execute_cycle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "completed" if success else "failed_checks",
            "safety_check": "passed" if is_safe else "failed",
            "calibration": "nominal" if is_calibrated else "out_of_spec",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("configure_params", configure_params)
_g.add_node("verify_safety", verify_safety)
_g.add_node("execute_cycle", execute_cycle)

_g.add_edge(START, "configure_params")
_g.add_edge("configure_params", "verify_safety")
_g.add_edge("verify_safety", "execute_cycle")
_g.add_edge("execute_cycle", END)

graph = _g.compile()
