# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181510 — Robot (segment 23).

Bespoke graph for robotic systems management, handling configuration
validation, kinematic profile assessment, and safety diagnostics.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181510"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181510"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Robot domain state
    config_valid: bool
    kinematics_ready: bool
    safety_diagnostics: dict[str, bool]
    payload_authorized: bool


def validate_robot_config(state: State) -> dict[str, Any]:
    """Validates the robot model, DOF, and baseline configuration."""
    inp = state.get("input") or {}
    model = inp.get("model_id")
    dof = inp.get("degrees_of_freedom", 0)

    # Robots in this segment typically require at least 4 DOF
    is_valid = bool(model) and int(dof) >= 4

    return {
        "log": [f"{UNISPSC_CODE}:validate_robot_config:model={model}:dof={dof}"],
        "config_valid": is_valid,
    }


def assess_kinematics(state: State) -> dict[str, Any]:
    """Evaluates the robot's kinematic profile and reachability constraints."""
    if not state.get("config_valid"):
        return {"log": [f"{UNISPSC_CODE}:assess_kinematics:skipped"]}

    inp = state.get("input") or {}
    reach = float(inp.get("max_reach_mm", 0))
    # Reachability is considered nominal if specified
    ready = reach > 0

    return {
        "log": [f"{UNISPSC_CODE}:assess_kinematics:reach={reach}mm"],
        "kinematics_ready": ready,
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Checks collision sensors, emergency stop status, and payload limits."""
    inp = state.get("input") or {}
    payload = float(inp.get("payload_kg", 0))

    # Safety logic: collision sensors must be active, payload within segment norms
    diagnostics = {
        "collision_sensors": inp.get("collision_sensors_active", True),
        "estop_status": inp.get("estop_nominal", True),
        "joint_limits": inp.get("joint_limits_configured", True)
    }

    authorized = payload <= 200.0  # Threshold for this agent's automated authorization

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_protocols:payload={payload}kg"],
        "safety_diagnostics": diagnostics,
        "payload_authorized": authorized,
    }


def emit_robot_status(state: State) -> dict[str, Any]:
    """Produces the final robotic operation readiness status."""
    diagnostics = state.get("safety_diagnostics", {})
    safety_ok = all(diagnostics.values()) and state.get("payload_authorized", False)
    ready = state.get("config_valid", False) and state.get("kinematics_ready", False) and safety_ok

    return {
        "log": [f"{UNISPSC_CODE}:emit_robot_status:ready={ready}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": ready,
            "readiness": {
                "operational": ready,
                "safety_cleared": safety_ok,
                "diagnostics": diagnostics,
                "status_code": "ROB-OK-100" if ready else "ROB-ERR-SAFETY"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_robot_config)
_g.add_node("kinematics", assess_kinematics)
_g.add_node("safety", verify_safety_protocols)
_g.add_node("emit", emit_robot_status)

_g.add_edge(START, "validate")
_g.add_edge("validate", "kinematics")
_g.add_edge("kinematics", "safety")
_g.add_edge("safety", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
