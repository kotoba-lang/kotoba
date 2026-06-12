# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121511 — Actuator (segment 20).

Bespoke graph logic for industrial actuators, managing calibration states,
position feedback, and force limits during mechanical execution cycles.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121511"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121511"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Actuator
    calibration_status: str
    position_feedback: float
    force_limit_reached: bool
    power_level: int


def validate_parameters(state: State) -> dict[str, Any]:
    """Ensures input parameters are within mechanical operating limits."""
    inp = state.get("input") or {}
    target_pos = inp.get("target_position", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "calibration_status": "CALIBRATED" if inp.get("calibrate") else "READY",
        "position_feedback": 0.0,
        "force_limit_reached": False,
        "power_level": inp.get("power", 100),
    }


def execute_actuation(state: State) -> dict[str, Any]:
    """Simulates the mechanical movement of the actuator."""
    inp = state.get("input") or {}
    target = inp.get("target_position", 1.0)

    # Simulate force limit check
    limit_hit = target > 100.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_actuation"],
        "position_feedback": target if not limit_hit else 100.0,
        "force_limit_reached": limit_hit,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Compiles the final actuator status and telemetry."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": state.get("calibration_status"),
            "final_position": state.get("position_feedback"),
            "safety_trip": state.get("force_limit_reached"),
            "ok": not state.get("force_limit_reached"),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("actuate", execute_actuation)
_g.add_node("emit", finalize_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "actuate")
_g.add_edge("actuate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
