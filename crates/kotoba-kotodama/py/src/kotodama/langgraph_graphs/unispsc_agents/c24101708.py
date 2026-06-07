# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101708 — Conveyor (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101708"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    belt_velocity: float
    is_loaded: bool
    motor_current: float
    safety_brake_active: bool


def verify_system_readiness(state: State) -> dict[str, Any]:
    """Initial check of conveyor hardware status."""
    inp = state.get("input") or {}
    load_present = inp.get("weight", 0.0) > 0.1
    return {
        "log": [f"{UNISPSC_CODE}:verify_system_readiness"],
        "is_loaded": load_present,
        "safety_brake_active": False,
    }


def activate_conveyor(state: State) -> dict[str, Any]:
    """Sets the belt in motion based on load status."""
    is_loaded = state.get("is_loaded", False)
    # Speed is higher when empty to clear the line
    velocity = 1.2 if is_loaded else 2.5
    # Amperage increases with load
    current = 15.5 if is_loaded else 8.2

    return {
        "log": [f"{UNISPSC_CODE}:activate_conveyor"],
        "belt_velocity": velocity,
        "motor_current": current,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Finalizes the transport event and reports metrics."""
    velocity = state.get("belt_velocity", 0.0)
    current = state.get("motor_current", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_summary": {
                "velocity_mps": velocity,
                "motor_load_amps": current,
                "status": "success" if velocity > 0 else "idle",
            },
        },
    }


_g = StateGraph(State)
_g.add_node("verify_system_readiness", verify_system_readiness)
_g.add_node("activate_conveyor", activate_conveyor)
_g.add_node("generate_telemetry", generate_telemetry)

_g.add_edge(START, "verify_system_readiness")
_g.add_edge("verify_system_readiness", "activate_conveyor")
_g.add_edge("activate_conveyor", "generate_telemetry")
_g.add_edge("generate_telemetry", END)

graph = _g.compile()
