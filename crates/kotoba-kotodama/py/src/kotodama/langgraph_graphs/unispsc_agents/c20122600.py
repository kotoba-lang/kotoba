# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122600"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Actuator
    target_position: float
    current_position: float
    system_pressure_psi: float
    calibration_verified: bool
    actuation_mode: str


def initialize_actuator(state: State) -> dict[str, Any]:
    """Parse instructions and prepare the actuator for movement."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    mode = str(inp.get("mode", "linear_servo"))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_actuator"],
        "target_position": target,
        "actuation_mode": mode,
        "current_position": state.get("current_position", 0.0),
    }


def verify_mechanical_integrity(state: State) -> dict[str, Any]:
    """Simulate pressure checks and calibration validation."""
    target = state.get("target_position", 0.0)
    # Simulated mechanical check: ensure target is within physical limits (0-100)
    is_safe = 0.0 <= target <= 100.0
    pressure = 92.4 if is_safe else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "system_pressure_psi": pressure,
        "calibration_verified": is_safe,
    }


def execute_actuation(state: State) -> dict[str, Any]:
    """Apply signal to the actuator and update physical position state."""
    if not state.get("calibration_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:actuation_aborted_safety"],
            "result": {
                "ok": False,
                "error": "Target outside safe mechanical range",
                "code": UNISPSC_CODE
            },
        }

    target = state.get("target_position", 0.0)
    return {
        "log": [f"{UNISPSC_CODE}:execute_actuation_complete"],
        "current_position": target,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": True,
            "final_position": target,
            "system_status": "nominal"
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_actuator)
_g.add_node("verify", verify_mechanical_integrity)
_g.add_node("actuate", execute_actuation)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "verify")
_g.add_edge("verify", "actuate")
_g.add_edge("actuate", END)

graph = _g.compile()
