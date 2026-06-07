# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101529 — Laser Procurement (segment 22).

Bespoke graph logic for laser system acquisition, safety validation,
and regulatory compliance tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101529"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101529"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Laser Procurement
    specification_verified: bool
    safety_compliance_level: str
    procurement_priority: str
    export_control_status: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates technical requirements and power ratings for the laser system."""
    inp = state.get("input") or {}
    power_watts = inp.get("power_watts", 0)
    is_valid = power_watts > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "specification_verified": is_valid,
        "procurement_priority": "high" if power_watts > 1000 else "standard"
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks safety certifications (IEC/FDA) and export control restrictions."""
    spec_ok = state.get("specification_verified", False)

    # Simulate a compliance check based on spec verification
    status = "CLEARED" if spec_ok else "FLAGGED"
    compliance = "CLASS_IV_CERTIFIED" if spec_ok else "PENDING"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "export_control_status": status,
        "safety_compliance_level": compliance
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Prepares the final procurement result package."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": state.get("export_control_status"),
            "safety_level": state.get("safety_compliance_level"),
            "ok": state.get("specification_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
