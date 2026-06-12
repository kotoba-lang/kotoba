# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121106 — Actuator (segment 20).

Bespoke graph for managing mechanical actuator states, including calibration,
movement execution, and position verification telemetry.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121106"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121106"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Actuator
    current_position_mm: float
    target_position_mm: float
    mechanical_load_n: float
    calibration_status: str


def calibrate(state: State) -> dict[str, Any]:
    """Initializes and calibrates the actuator mechanism."""
    inp = state.get("input") or {}
    target = float(inp.get("target_position", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:calibrate -> target set to {target}mm"],
        "target_position_mm": target,
        "calibration_status": "CALIBRATED",
        "current_position_mm": 0.0,
    }


def execute_movement(state: State) -> dict[str, Any]:
    """Simulates the physical movement of the actuator to the target position."""
    target = state.get("target_position_mm", 0.0)
    # Simulate mechanical drive logic
    return {
        "log": [f"{UNISPSC_CODE}:execute_movement -> driving mechanism to {target}mm"],
        "current_position_mm": target,
        "mechanical_load_n": 12.4,  # Simulated resistance/load
    }


def verify_telemetry(state: State) -> dict[str, Any]:
    """Verifies position feedback and emits the final telemetry result."""
    pos = state.get("current_position_mm", 0.0)
    load = state.get("mechanical_load_n", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_telemetry -> position {pos}mm confirmed"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_position_mm": pos,
                "measured_load_n": load,
                "operational_mode": "ACTIVE_HOLD"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate", calibrate)
_g.add_node("execute_movement", execute_movement)
_g.add_node("verify_telemetry", verify_telemetry)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "execute_movement")
_g.add_edge("execute_movement", "verify_telemetry")
_g.add_edge("verify_telemetry", END)

graph = _g.compile()
