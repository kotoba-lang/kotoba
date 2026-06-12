# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23161606 — Robot (segment 23).
Bespoke graph logic for industrial robot kinematic validation, safety zone
monitoring, and payload throughput estimation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23161606"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23161606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for "Robot"
    robot_model: str
    payload_capacity_kg: float
    safety_zone_status: str
    kinematic_valid: bool
    estimated_cycle_time: float


def configure_robot_parameters(state: State) -> dict[str, Any]:
    """Sets initial robot configuration from input data."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:configure_robot_parameters"],
        "robot_model": inp.get("model", "IRB-STANDARD-X1"),
        "payload_capacity_kg": float(inp.get("payload", 10.0)),
        "safety_zone_status": "initializing",
        "kinematic_valid": False,
        "estimated_cycle_time": 0.0,
    }


def validate_kinematics_and_safety(state: State) -> dict[str, Any]:
    """Validates reachability and safety constraints for the robot."""
    inp = state.get("input") or {}
    points = inp.get("target_points", [])

    # Simple logic: need at least one target point to be kinematically valid
    valid = len(points) > 0
    safety = "secure" if inp.get("guarding_active", True) else "breached"

    return {
        "log": [f"{UNISPSC_CODE}:validate_kinematics_and_safety:valid={valid}"],
        "kinematic_valid": valid,
        "safety_zone_status": safety,
    }


def calculate_throughput(state: State) -> dict[str, Any]:
    """Estimates robot cycle time based on payload and safety status."""
    if not state.get("kinematic_valid") or state.get("safety_zone_status") != "secure":
        return {
            "log": [f"{UNISPSC_CODE}:calculate_throughput:inhibited"],
            "estimated_cycle_time": -1.0,
        }

    payload = state.get("payload_capacity_kg", 0.0)
    # Heuristic: heavier payload increases cycle time
    cycle_time = 1.5 + (payload * 0.1)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_throughput:time={cycle_time}"],
        "estimated_cycle_time": cycle_time,
    }


def emit_robot_readiness(state: State) -> dict[str, Any]:
    """Produces the final readiness and telemetry for the robot agent."""
    cycle_time = state.get("estimated_cycle_time", 0.0)
    ok = cycle_time > 0

    return {
        "log": [f"{UNISPSC_CODE}:emit_robot_readiness"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "robot_telemetry": {
                "model": state.get("robot_model"),
                "cycle_time_sec": cycle_time,
                "safety": state.get("safety_zone_status"),
                "payload_kg": state.get("payload_capacity_kg"),
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_robot_parameters)
_g.add_node("validate", validate_kinematics_and_safety)
_g.add_node("throughput", calculate_throughput)
_g.add_node("emit", emit_robot_readiness)

_g.add_edge(START, "configure")
_g.add_edge("configure", "validate")
_g.add_edge("validate", "throughput")
_g.add_edge("throughput", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
