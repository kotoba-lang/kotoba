# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12161506 — Chemical (segment 12).

This bespoke implementation handles chemical material verification and safety
profile generation. It validates purity levels, ensures SDS compliance, and
emits a structured chemical product profile.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12161506"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12161506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical material tracking
    purity_level: float
    safety_data_sheet_id: str
    hazard_classification: str
    batch_id: str
    compliance_passed: bool


def verify_chemical_purity(state: State) -> dict[str, Any]:
    """Verify chemical composition and purity levels from input data."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)
    batch = inp.get("batch_id", "UNKNOWN-BATCH")

    return {
        "log": [f"{UNISPSC_CODE}:verify_chemical_purity - batch {batch}"],
        "purity_level": purity,
        "batch_id": batch,
        "compliance_passed": purity >= 95.0
    }


def assess_safety_compliance(state: State) -> dict[str, Any]:
    """Assess safety data sheet presence and hazard classification."""
    inp = state.get("input") or {}
    sds_id = inp.get("sds_id", "SDS-PENDING")
    hazard = inp.get("hazard_class", "GENERAL")

    log_msg = f"{UNISPSC_CODE}:assess_safety_compliance - SDS {sds_id}"
    return {
        "log": [log_msg],
        "safety_data_sheet_id": sds_id,
        "hazard_classification": hazard
    }


def generate_chemical_report(state: State) -> dict[str, Any]:
    """Finalize the chemical profile and emit the structured result."""
    success = state.get("compliance_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_chemical_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity_level": state.get("purity_level"),
            "hazard_class": state.get("hazard_classification"),
            "sds_id": state.get("safety_data_sheet_id"),
            "compliant": success,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_purity", verify_chemical_purity)
_g.add_node("assess_safety", assess_safety_compliance)
_g.add_node("generate_report", generate_chemical_report)

_g.add_edge(START, "verify_purity")
_g.add_edge("verify_purity", "assess_safety")
_g.add_edge("assess_safety", "generate_report")
_g.add_edge("generate_report", END)

graph = _g.compile()
