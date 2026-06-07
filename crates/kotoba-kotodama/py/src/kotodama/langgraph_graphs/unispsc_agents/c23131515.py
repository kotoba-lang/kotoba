# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23131515 — Robot Spec (segment 23).
Bespoke implementation for robot technical specification analysis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23131515"
UNISPSC_TITLE = "Robot Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23131515"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Robot Spec
    payload_capacity_kg: float
    degrees_of_freedom: int
    is_compliant: bool
    safety_category: str


def validate_robot_spec(state: State) -> dict[str, Any]:
    """Validates the input robot configuration against mandatory safety standards."""
    inp = state.get("input") or {}
    payload = float(inp.get("payload", 0.0))
    dof = int(inp.get("dof", 6))

    return {
        "log": [f"{UNISPSC_CODE}:validate_robot_spec"],
        "payload_capacity_kg": payload,
        "degrees_of_freedom": dof,
        "is_compliant": payload > 0 and dof > 0,
    }


def analyze_kinematics(state: State) -> dict[str, Any]:
    """Simulates kinematic analysis and determines the safety category."""
    dof = state.get("degrees_of_freedom", 0)
    category = "Standard"
    if dof > 7:
        category = "Advanced/Redundant"
    elif dof < 3:
        category = "Simple/Linear"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_kinematics"],
        "safety_category": category,
    }


def compile_spec_report(state: State) -> dict[str, Any]:
    """Finalizes the technical specification and generates the actor response."""
    return {
        "log": [f"{UNISPSC_CODE}:compile_spec_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "payload_kg": state.get("payload_capacity_kg"),
                "dof": state.get("degrees_of_freedom"),
                "safety_class": state.get("safety_category"),
                "compliance_status": "APPROVED" if state.get("is_compliant") else "REJECTED"
            },
            "ok": state.get("is_compliant", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_robot_spec)
_g.add_node("analyze", analyze_kinematics)
_g.add_node("report", compile_spec_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "report")
_g.add_edge("report", END)

graph = _g.compile()
