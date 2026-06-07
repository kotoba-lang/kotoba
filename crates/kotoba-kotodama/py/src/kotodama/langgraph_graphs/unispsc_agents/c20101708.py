# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101708 — Robot Arm (segment 20).

Bespoke logic for controlling and monitoring a robotic arm assembly,
ensuring safety constraints and kinematic validation for industrial automation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101708"
UNISPSC_TITLE = "Robot Arm"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific Robot Arm state fields
    kinematics_verified: bool
    payload_kg: float
    joint_angles: list[float]
    safety_lock_active: bool


def calibrate_and_safety_check(state: State) -> dict[str, Any]:
    """
    Initializes system state, reads payload sensors, and verifies
    that the emergency stop is not engaged.
    """
    inp = state.get("input") or {}
    payload = float(inp.get("payload_weight", 0.0))
    emergency_stop = inp.get("estop_active", False)

    # Safety logic: Excessive payload or explicit E-Stop triggers safety lock
    lock_engaged = payload > 150.0 or emergency_stop

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_and_safety_check"],
        "payload_kg": payload,
        "safety_lock_active": lock_engaged,
    }


def compute_inverse_kinematics(state: State) -> dict[str, Any]:
    """
    Calculates the required joint angles for the target destination
    only if the safety system is clear.
    """
    if state.get("safety_lock_active"):
        return {
            "log": [f"{UNISPSC_CODE}:compute_kinematics_inhibited_by_safety"],
            "kinematics_verified": False,
        }

    # Simulation of a 6-axis inverse kinematics solver result
    simulated_angles = [0.0, 15.5, -45.0, 90.0, 0.0, 10.0]

    return {
        "log": [f"{UNISPSC_CODE}:compute_kinematics_success"],
        "joint_angles": simulated_angles,
        "kinematics_verified": True,
    }


def execute_arm_sequence(state: State) -> dict[str, Any]:
    """
    Finalizes the robot operation sequence and emits telemetry
    data reflecting the execution status.
    """
    verified = state.get("kinematics_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:execute_arm_sequence"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "success" if verified else "aborted_safety_protocol",
            "telemetry": {
                "final_payload": state.get("payload_kg"),
                "resolved_joints": state.get("joint_angles"),
            },
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("safety_check", calibrate_and_safety_check)
_g.add_node("kinematics", compute_inverse_kinematics)
_g.add_node("execute", execute_arm_sequence)

_g.add_edge(START, "safety_check")
_g.add_edge("safety_check", "kinematics")
_g.add_edge("kinematics", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
