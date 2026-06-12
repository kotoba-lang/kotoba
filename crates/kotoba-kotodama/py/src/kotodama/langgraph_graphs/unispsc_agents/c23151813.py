# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151813 — Actuator (segment 23).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151813"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151813"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    target_position: float
    force_limit: float
    system_status: str
    calibration_success: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Extracts and validates actuation parameters from input."""
    inp = state.get("input") or {}
    target = float(inp.get("target", 0.0))
    limit = float(inp.get("limit", 100.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "target_position": target,
        "force_limit": limit,
        "system_status": "parameters_validated"
    }


def verify_alignment(state: State) -> dict[str, Any]:
    """Simulates physical alignment and calibration check of the actuator."""
    # Basic logic: ensure force limits are within operating safety margins
    limit = state.get("force_limit", 0.0)
    success = 0.0 < limit <= 500.0
    return {
        "log": [f"{UNISPSC_CODE}:verify_alignment"],
        "calibration_success": success,
        "system_status": "alignment_verified" if success else "alignment_failed"
    }


def perform_actuation(state: State) -> dict[str, Any]:
    """Simulates the physical movement or torque application."""
    target = state.get("target_position", 0.0)
    is_ready = state.get("calibration_success", False)

    if is_ready:
        status = "actuation_complete"
        final_pos = target
    else:
        status = "actuation_aborted_safety_lock"
        final_pos = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_actuation"],
        "system_status": status,
        "result": {
            "final_position": final_pos,
            "status_code": status
        }
    }


def emit_telemetry(state: State) -> dict[str, Any]:
    """Finalizes the response with UNISPSC metadata and execution result."""
    res = state.get("result") or {}
    success = state.get("system_status") == "actuation_complete"
    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry"],
        "result": {
            **res,
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("verify", verify_alignment)
_g.add_node("actuate", perform_actuation)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "actuate")
_g.add_edge("actuate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
