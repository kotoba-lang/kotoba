# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171602 — Transportation Components.

This bespoke graph manages state transitions for vehicle universal joints,
including specification validation, load-bearing analysis, and component
certification within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171602"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for universal joints / vehicle components
    torque_capacity_nm: float
    alignment_angle_deg: float
    integrity_verified: bool
    maintenance_status: str


def validate_joint_spec(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the universal joint."""
    inp = state.get("input") or {}
    torque = float(inp.get("torque", 0.0))
    angle = float(inp.get("angle", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_joint_spec"],
        "torque_capacity_nm": torque,
        "alignment_angle_deg": angle,
        "integrity_verified": torque > 0 and abs(angle) < 45.0,
    }


def analyze_load_bearing(state: State) -> dict[str, Any]:
    """Simulates analysis of load-bearing performance under torque."""
    is_valid = state.get("integrity_verified", False)
    torque = state.get("torque_capacity_nm", 0.0)

    status = "nominal" if is_valid and torque < 5000 else "stress_limit_warning"
    if not is_valid:
        status = "failed_validation"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_bearing"],
        "maintenance_status": status,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the state and emits the component certification result."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": state.get("integrity_verified", False),
            "telemetry": {
                "torque": state.get("torque_capacity_nm"),
                "angle": state.get("alignment_angle_deg"),
                "status": state.get("maintenance_status"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_joint_spec)
_g.add_node("analyze", analyze_load_bearing)
_g.add_node("certify", certify_component)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
