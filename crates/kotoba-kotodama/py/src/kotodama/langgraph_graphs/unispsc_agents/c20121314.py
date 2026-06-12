# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121314"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121314"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    target_displacement: float
    force_limit_newtons: float
    safety_check_passed: bool
    current_status: str


def analyze_instruction(state: State) -> dict[str, Any]:
    """
    Parses the incoming control instruction for the Actuator.
    In segment 20 (Mining/Drilling), actuators often require precision setpoints.
    """
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    limit = float(inp.get("force_limit", 500.0))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_instruction -> target: {target}mm"],
        "target_displacement": target,
        "force_limit_newtons": limit,
        "current_status": "analyzed",
    }


def verify_safety_envelope(state: State) -> dict[str, Any]:
    """
    Checks if the requested motion is within safe operating parameters for mining machinery.
    """
    limit = state.get("force_limit_newtons", 0.0)
    # Threshold for hydraulic/mechanical actuators in heavy drilling environments
    passed = limit <= 2500.0
    status = "safe" if passed else "unsafe_force_threshold"
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_envelope -> {status}"],
        "safety_check_passed": passed,
        "current_status": status,
    }


def execute_activation(state: State) -> dict[str, Any]:
    """
    Simulates the physical displacement of the actuator rod/assembly.
    """
    if not state.get("safety_check_passed"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_activation -> safety_interlock_blocked"],
            "current_status": "blocked",
        }

    return {
        "log": [f"{UNISPSC_CODE}:execute_activation -> motion_applied"],
        "current_status": "completed",
    }


def package_telemetry(state: State) -> dict[str, Any]:
    """
    Assembles the final execution report for the UnispscAgentExecutorCell.
    """
    status = state.get("current_status")
    success = status == "completed"
    return {
        "log": [f"{UNISPSC_CODE}:package_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_status": status,
                "displacement_mm": state.get("target_displacement") if success else 0.0,
                "force_limit": state.get("force_limit_newtons"),
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_instruction)
_g.add_node("safety", verify_safety_envelope)
_g.add_node("activate", execute_activation)
_g.add_node("emit", package_telemetry)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "safety")
_g.add_edge("safety", "activate")
_g.add_edge("activate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
