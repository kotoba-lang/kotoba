# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181509 — Robot (segment 23).
Bespoke logic for kinematic validation, safety interlock verification, and operational readiness.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181509"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Robot domain state
    kinematics_valid: bool
    safety_certified: bool
    power_profile: str
    dof_verified: int


def validate_kinematics(state: State) -> dict[str, Any]:
    """Ensures the robot configuration contains valid kinematic parameters."""
    inp = state.get("input") or {}
    dof = inp.get("degrees_of_freedom", 0)
    reach = inp.get("reach_mm", 0)
    is_valid = dof >= 3 and reach > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_kinematics"],
        "kinematics_valid": is_valid,
        "dof_verified": dof,
    }


def verify_safety_interlocks(state: State) -> dict[str, Any]:
    """Validates presence of mandatory industrial safety protocols."""
    if not state.get("kinematics_valid"):
        return {"log": [f"{UNISPSC_CODE}:verify_safety:denied_precheck"]}

    inp = state.get("input") or {}
    has_estop = inp.get("emergency_stop", False)
    has_collision = inp.get("collision_detection", False)
    ok = has_estop and has_collision

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_interlocks"],
        "safety_certified": ok,
        "power_profile": "ISO-10218-1-High" if state.get("dof_verified", 0) > 6 else "ISO-10218-1-Standard"
    }


def compile_robot_certificate(state: State) -> dict[str, Any]:
    """Constructs the finalized robot operational certificate."""
    ok = state.get("kinematics_valid", False) and state.get("safety_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:compile_robot_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": ok,
            "payload": {
                "safety_status": "CERTIFIED" if ok else "FAILED",
                "power_compliance": state.get("power_profile"),
                "dof": state.get("dof_verified")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_kinematics", validate_kinematics)
_g.add_node("verify_safety_interlocks", verify_safety_interlocks)
_g.add_node("compile_robot_certificate", compile_robot_certificate)

_g.add_edge(START, "validate_kinematics")
_g.add_edge("validate_kinematics", "verify_safety_interlocks")
_g.add_edge("verify_safety_interlocks", "compile_robot_certificate")
_g.add_edge("compile_robot_certificate", END)

graph = _g.compile()
