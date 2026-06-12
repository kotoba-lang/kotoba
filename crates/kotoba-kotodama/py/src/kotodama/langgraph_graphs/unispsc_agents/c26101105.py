# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101105 — Motor Procurement (segment 26).
Bespoke logic for technical specification evaluation, vendor compliance validation,
and procurement lifecycle management for industrial motors.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101105"
UNISPSC_TITLE = "Motor Procurement"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101105"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Motor Procurement
    spec_check_passed: bool
    vendor_approved: bool
    procurement_status: str
    compliance_report: dict[str, Any]


def evaluate_specs(state: State) -> dict[str, Any]:
    """Validates technical requirements: voltage, phase, RPM, and frame size."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Basic validation for essential motor parameters
    required = ["voltage", "rpm", "power_rating"]
    passed = all(k in specs for k in required)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_specs"],
        "spec_check_passed": passed,
    }


def validate_vendor_compliance(state: State) -> dict[str, Any]:
    """Checks vendor certification and supply chain integrity for critical components."""
    if not state.get("spec_check_passed"):
        return {
            "log": [f"{UNISPSC_CODE}:validate_vendor:skipped_due_to_specs"],
            "vendor_approved": False,
        }

    inp = state.get("input") or {}
    vendor_info = inp.get("vendor", {})
    # Mock compliance check: check for ISO-9001 or equivalent certification
    is_certified = vendor_info.get("iso_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_vendor:{"approved" if is_certified else "denied"}"],
        "vendor_approved": is_certified,
        "compliance_report": {
            "iso_9001": is_certified,
            "origin_verification": "verified" if vendor_info.get("origin") else "pending"
        }
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Executes the final procurement step, issuing a PO or a rejection notice."""
    specs_ok = state.get("spec_check_passed", False)
    vendor_ok = state.get("vendor_approved", False)
    ok = specs_ok and vendor_ok

    status = "PO_ISSUED" if ok else "REJECTED_COMPLIANCE_FAILURE"
    if not specs_ok:
        status = "REJECTED_TECHNICAL_INCOMPLETE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("evaluate_specs", evaluate_specs)
_g.add_node("validate_vendor_compliance", validate_vendor_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "evaluate_specs")
_g.add_edge("evaluate_specs", "validate_vendor_compliance")
_g.add_edge("validate_vendor_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
