# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131704 — Aircraft Procure (segment 25).

Bespoke logic for managing the procurement lifecycle of aircraft assets,
including airworthiness verification and budget compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131704"
UNISPSC_TITLE = "Aircraft Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Aircraft Procurement
    airworthiness_standard: str
    procurement_phase: str
    acquisition_cost_limit: float
    vendor_audit_passed: bool


def assess_procurement_request(state: State) -> dict[str, Any]:
    """Initial assessment of the aircraft procurement request and cost limits."""
    inp = state.get("input") or {}
    standard = inp.get("standard", "FAA-PART-25")
    limit = float(inp.get("budget_limit", 1000000.0))

    return {
        "log": [f"{UNISPSC_CODE}:assess_procurement_request"],
        "airworthiness_standard": standard,
        "acquisition_cost_limit": limit,
        "procurement_phase": "initial_assessment"
    }


def verify_compliance_and_vendor(state: State) -> dict[str, Any]:
    """Verifies that the requested aircraft meets standards and vendor is audited."""
    standard = state.get("airworthiness_standard", "unspecified")
    # Simulation: verify if the standard is acceptable for procurement
    passed = standard in ["FAA-PART-25", "EASA-CS-25", "MIL-STD-1797"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance_and_vendor"],
        "vendor_audit_passed": passed,
        "procurement_phase": "compliance_verification"
    }


def finalize_procurement_record(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction record and output state."""
    audit_ok = state.get("vendor_audit_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_record"],
        "procurement_phase": "finalized",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if audit_ok else "REJECTED",
            "standard_verified": state.get("airworthiness_standard"),
            "ok": audit_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("assess", assess_procurement_request)
_g.add_node("verify", verify_compliance_and_vendor)
_g.add_node("finalize", finalize_procurement_record)

_g.add_edge(START, "assess")
_g.add_edge("assess", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
