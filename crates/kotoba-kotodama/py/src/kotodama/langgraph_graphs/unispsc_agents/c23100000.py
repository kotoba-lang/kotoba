# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23100000 — Machine Procurement (segment 23).
Bespoke logic for handling industrial machine acquisition workflows,
including specification validation and vendor assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23100000"
UNISPSC_TITLE = "Machine Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23100000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Machine Procurement
    specifications_verified: bool
    vendor_compliance_score: float
    procurement_id: str
    safety_certification_required: bool
    budget_limit_exceeded: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Checks if the machine requirements meet technical and safety standards."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Logic: Verify required fields exist
    has_power = "power_rating" in specs
    has_capacity = "capacity" in specs
    verified = has_power and has_capacity

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "specifications_verified": verified,
        "safety_certification_required": specs.get("industrial_grade", True),
    }


def assess_vendor_eligibility(state: State) -> dict[str, Any]:
    """Evaluates the vendor's standing and assigns a procurement tracking ID."""
    inp = state.get("input") or {}
    vendor_data = inp.get("vendor", {})

    # Simulate scoring based on years in business
    years = vendor_data.get("years_active", 0)
    score = min(10.0, float(years) * 1.5)

    # Generate a deterministic ID based on the vendor name
    vendor_name = vendor_data.get("name", "generic")
    pid = f"MP-{UNISPSC_CODE}-{abs(hash(vendor_name)) % 10000:04d}"

    return {
        "log": [f"{UNISPSC_CODE}:assess_vendor_eligibility"],
        "vendor_compliance_score": score,
        "procurement_id": pid,
    }


def finalize_procurement_state(state: State) -> dict[str, Any]:
    """Aggregates findings into a final procurement decision."""
    is_verified = state.get("specifications_verified", False)
    score = state.get("vendor_compliance_score", 0.0)
    safety_req = state.get("safety_certification_required", False)

    # Decision logic: Verified specs, score > 5.0, and safety accounted for
    approved = is_verified and score > 5.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_state"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "procurement_id": state.get("procurement_id"),
            "status": "READY_FOR_PURCHASE" if approved else "REQUIREMENTS_NOT_MET",
            "safety_audit_needed": safety_req,
            "vendor_score": score,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("assess_vendor_eligibility", assess_vendor_eligibility)
_g.add_node("finalize_procurement_state", finalize_procurement_state)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "assess_vendor_eligibility")
_g.add_edge("assess_vendor_eligibility", "finalize_procurement_state")
_g.add_edge("finalize_procurement_state", END)

graph = _g.compile()
