# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101601 — Truck Procurement (segment 25).

Bespoke graph logic for managing truck fleet acquisition workflows,
including requirement validation, vendor selection, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101601"
UNISPSC_TITLE = "Truck Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Truck Procurement
    fleet_requirements: dict[str, Any]
    vendor_scoring: dict[str, float]
    compliance_audit_passed: bool
    procurement_stage: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Analyzes input to define truck specifications and fleet needs."""
    inp = state.get("input") or {}
    requirements = inp.get("requirements", {
        "payload_capacity": "heavy",
        "engine_type": "diesel",
        "quantity": 1
    })
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "fleet_requirements": requirements,
        "compliance_audit_passed": True,
        "procurement_stage": "requirements_validated"
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Simulates the evaluation of truck manufacturers and dealers."""
    reqs = state.get("fleet_requirements", {})
    # Mock scoring logic based on requirements
    payload = reqs.get("payload_capacity", "standard")
    scores = {
        "TitanTrucks": 0.95 if payload == "heavy" else 0.80,
        "SwiftHaulers": 0.85,
        "EcoFreight": 0.70
    }
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_scoring": scores,
        "procurement_stage": "vendor_evaluation_complete"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Issues the final procurement result and selected vendor details."""
    scores = state.get("vendor_scoring", {})
    selected_vendor = max(scores.items(), key=lambda x: x[1])[0] if scores else "Unknown"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_stage": "completed",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "selected_vendor": selected_vendor,
            "audit_status": "passed" if state.get("compliance_audit_passed") else "pending",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("evaluate_vendors", evaluate_vendors)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "evaluate_vendors")
_g.add_edge("evaluate_vendors", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
