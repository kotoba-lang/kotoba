# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153410 — Robot Procurement (segment 23).

Bespoke graph logic for industrial robot procurement workflows, including
specification validation, vendor vetting, and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153410"
UNISPSC_TITLE = "Robot Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153410"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Robot Procurement
    procurement_specs: dict[str, Any]
    vendor_vetted: bool
    procurement_id: str
    compliance_status: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the robot specifications against procurement standards."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Check for critical robot specs: DOF (Degrees of Freedom), Payload, Reach
    has_specs = all(k in specs for k in ["dof", "payload_kg", "reach_mm"])
    status = "VALIDATED" if has_specs else "INCOMPLETE_SPECS"

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements:{status}"],
        "procurement_specs": specs,
        "compliance_status": status,
    }


def vet_robot_vendor(state: State) -> dict[str, Any]:
    """Performs automated vendor vetting based on the procurement ID or input."""
    inp = state.get("input") or {}
    vendor_id = inp.get("vendor_id", "VENDOR-UNKNOWN")

    # Simulate a vetting process for robotic systems providers
    is_authorized = vendor_id.startswith("ROB-") or vendor_id == "GLOBAL-BOTS-001"

    return {
        "log": [f"{UNISPSC_CODE}:vet_robot_vendor:{vendor_id}:{is_authorized}"],
        "vendor_vetted": is_authorized,
        "procurement_id": f"PROC-23-{UNISPSC_CODE}-AX100",
    }


def finalize_procurement_order(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and prepares the actor result."""
    vetted = state.get("vendor_vetted", False)
    compliant = state.get("compliance_status") == "VALIDATED"
    success = vetted and compliant

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_order:success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "APPROVED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("vet", vet_robot_vendor)
_g.add_node("finalize", finalize_procurement_order)

_g.add_edge(START, "validate")
_g.add_edge("validate", "vet")
_g.add_edge("vet", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
