# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122606 — Actuator (segment 20).

Bespoke graph for controlling and monitoring mechanical actuators.
This agent handles target validation, actuation simulation, and telemetry reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122606"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    current_position: float
    target_position: float
    torque_nm: float
    operational_status: str


def validate_command(state: State) -> dict[str, Any]:
    """Validates the input command and sets the target position."""
    inp = state.get("input") or {}
    # Default to 0.0 if not provided
    target = float(inp.get("target_position", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_command"],
        "target_position": target,
        "operational_status": "READY",
    }


def simulate_actuation(state: State) -> dict[str, Any]:
    """Simulates mechanical movement towards the target position."""
    target = state.get("target_position", 0.0)
    # In a real system, this would interface with hardware or a physics engine.
    # Here we simulate an immediate transition to the target state.
    return {
        "log": [f"{UNISPSC_CODE}:simulate_actuation"],
        "current_position": target,
        "torque_nm": 18.2,  # Representative operational torque
        "operational_status": "MOVING",
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final telemetry report for the actuator."""
    pos = state.get("current_position", 0.0)
    torque = state.get("torque_nm", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "operational_status": "IDLE",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_position": pos,
                "measured_torque": torque,
                "completion_status": "SUCCESS"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_command", validate_command)
_g.add_node("simulate_actuation", simulate_actuation)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "validate_command")
_g.add_edge("validate_command", "simulate_actuation")
_g.add_edge("simulate_actuation", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
