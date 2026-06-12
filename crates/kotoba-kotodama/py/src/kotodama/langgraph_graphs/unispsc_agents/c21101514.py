# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101514 — Excavator (segment 21).
Bespoke logic for simulated heavy machinery operation and telemetry.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101514"
UNISPSC_TITLE = "Excavator"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific excavator state
    hydraulic_pressure_psi: int
    safety_lock_engaged: bool
    bucket_capacity_m3: float
    current_dig_depth_m: float
    engine_hours: float


def pre_operation_check(state: State) -> dict[str, Any]:
    """Perform initial safety and hydraulic system checks."""
    inp = state.get("input") or {}
    # Simulate system initialization
    target_pressure = inp.get("target_pressure", 2800)
    safety_status = inp.get("safety_override", False) is False

    return {
        "log": [f"{UNISPSC_CODE}:pre_operation_check"],
        "hydraulic_pressure_psi": target_pressure,
        "safety_lock_engaged": safety_status,
        "bucket_capacity_m3": 1.5,
        "engine_hours": 1240.5,
    }


def excavation_cycle(state: State) -> dict[str, Any]:
    """Execute a simulated digging cycle if safety protocols allow."""
    if not state.get("safety_lock_engaged"):
        return {"log": [f"{UNISPSC_CODE}:excavation_cycle_blocked_safety"]}

    # Simulate digging to a specific depth
    requested_depth = (state.get("input") or {}).get("depth", 2.0)

    return {
        "log": [f"{UNISPSC_CODE}:excavation_cycle_executed"],
        "current_dig_depth_m": float(requested_depth),
    }


def generate_report(state: State) -> dict[str, Any]:
    """Compile the final operation report and telemetry data."""
    is_safe = state.get("safety_lock_engaged", False)
    depth = state.get("current_dig_depth_m", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "SUCCESS" if is_safe and depth > 0 else "INCOMPLETE",
            "telemetry": {
                "final_depth_m": depth,
                "pressure_psi": state.get("hydraulic_pressure_psi"),
                "engine_hours": state.get("engine_hours"),
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("pre_operation_check", pre_operation_check)
_g.add_node("excavation_cycle", excavation_cycle)
_g.add_node("generate_report", generate_report)

_g.add_edge(START, "pre_operation_check")
_g.add_edge("pre_operation_check", "excavation_cycle")
_g.add_edge("excavation_cycle", "generate_report")
_g.add_edge("generate_report", END)

graph = _g.compile()
