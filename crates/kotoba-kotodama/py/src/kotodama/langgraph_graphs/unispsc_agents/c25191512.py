# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191512 — Airstairs (segment 25).

Bespoke ground support equipment logic for managing mobile aircraft stairs.
This agent handles specifications validation, mechanical deployment simulation,
and safety interlock verification for aircraft boarding operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191512"
UNISPSC_TITLE = "Airstairs"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191512"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields
    aircraft_model: str
    target_threshold_height: float
    safety_interlocks_active: bool
    deployment_verified: bool
    chassis_stabilized: bool


def validate_aircraft_compatibility(state: State) -> dict[str, Any]:
    """Inspects input for aircraft type and determines required stair height."""
    inp = state.get("input") or {}
    model = str(inp.get("aircraft_model", "unknown")).upper()
    height = float(inp.get("threshold_height_meters", 3.4))

    # Support logic for common narrow-body and regional aircraft
    supported_models = ["B737", "A320", "CRJ", "ERJ", "MD80"]
    compatible = any(m in model for m in supported_models)

    return {
        "log": [f"{UNISPSC_CODE}:validate_aircraft_compatibility"],
        "aircraft_model": model,
        "target_threshold_height": height,
        "deployment_verified": compatible,
    }


def simulate_mechanical_deployment(state: State) -> dict[str, Any]:
    """Simulates the physical extension of the stairs and stabilization."""
    is_compatible = state.get("deployment_verified", False)
    if not is_compatible:
        return {
            "log": [f"{UNISPSC_CODE}:deployment_halted_incompatible_model"],
            "chassis_stabilized": False,
            "safety_interlocks_active": False,
        }

    # Simulate extension sequence
    return {
        "log": [f"{UNISPSC_CODE}:simulate_mechanical_deployment"],
        "chassis_stabilized": True,
        "safety_interlocks_active": True,
    }


def finalize_ground_operation(state: State) -> dict[str, Any]:
    """Confirms final status and emits the operation result."""
    success = (
        state.get("deployment_verified", False)
        and state.get("chassis_stabilized", False)
        and state.get("safety_interlocks_active", False)
    )

    status_msg = "Ready for boarding" if success else "Operational failure"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_ground_operation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operation_status": status_msg,
            "aircraft": state.get("aircraft_model"),
            "height_set": state.get("target_threshold_height"),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_aircraft_compatibility)
_g.add_node("deploy", simulate_mechanical_deployment)
_g.add_node("finalize", finalize_ground_operation)

_g.add_edge(START, "validate")
_g.add_edge("validate", "deploy")
_g.add_edge("deploy", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
