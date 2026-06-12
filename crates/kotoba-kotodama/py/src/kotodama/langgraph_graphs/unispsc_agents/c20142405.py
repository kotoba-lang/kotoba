# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142405 — Robot Procurement (segment 20).

Bespoke graph logic for handling technical specifications, safety compliance,
and vendor selection for specialized robotic equipment procurement.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142405"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142405"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Robot Procurement
    robot_type: str
    safety_certification: bool
    procurement_id: str
    budget_approved: bool
    technical_specs_verified: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the technical requirements and robot type for the procurement."""
    inp = state.get("input") or {}
    robot_type = inp.get("robot_type", "unspecified")
    specs = inp.get("specs", {})

    # Simple validation logic for robot procurement
    valid = bool(robot_type and specs)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "robot_type": robot_type,
        "technical_specs_verified": valid,
        "budget_approved": inp.get("budget", 0) > 0,
    }


def audit_compliance(state: State) -> dict[str, Any]:
    """Ensures the robot meets safety standards and regulatory compliance."""
    # Simulation of compliance check (e.g., ISO 10218 for industrial robots)
    is_compliant = state.get("technical_specs_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:audit_compliance"],
        "safety_certification": is_compliant,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and generates the result artifact."""
    robot_type = state.get("robot_type", "unknown")
    success = state.get("safety_certification", False) and state.get("budget_approved", False)

    proc_id = f"ROB-{UNISPSC_CODE}-{id(state) % 10000:04d}"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_id": proc_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "procurement_id": proc_id,
            "robot_type": robot_type,
            "status": "APPROVED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requirements", validate_requirements)
_g.add_node("audit_compliance", audit_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "audit_compliance")
_g.add_edge("audit_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
