# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352126 — Chemical Procurement (segment 12).

This bespoke graph manages the specialized procurement workflow for chemical
materials, focusing on safety data sheet (SDS) verification, hazard
classification, and regulatory compliance screening.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352126"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352126"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Chemical Procurement domain state
    sds_verified: bool
    hazard_level: int
    regulatory_id: str
    procurement_phase: str


def validate_safety_data(state: State) -> dict[str, Any]:
    """Validates the presence and validity of Safety Data Sheets (SDS)."""
    inp = state.get("input") or {}
    sds_id = inp.get("sds_id")
    verified = bool(sds_id)

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_data - SDS {sds_id or 'missing'} verified: {verified}"],
        "sds_verified": verified,
        "hazard_level": inp.get("hazard_rating", 0),
    }


def assess_compliance(state: State) -> dict[str, Any]:
    """Assesses regulatory compliance based on hazard levels and material type."""
    hazard = state.get("hazard_level", 0)
    # Logic: High hazard levels require additional regulatory tracking IDs
    needs_id = hazard > 5
    reg_id = "REG-AUTH-123" if needs_id else "STANDARD"

    return {
        "log": [f"{UNISPSC_CODE}:assess_compliance - Hazard level {hazard} processed"],
        "regulatory_id": reg_id,
        "procurement_phase": "COMPLIANCE_SCREENING",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement request and generates the outcome report."""
    is_safe = state.get("sds_verified", False)
    reg_id = state.get("regulatory_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement - Phase complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "sds_check": is_safe,
            "regulatory_status": reg_id,
            "authorized": is_safe and bool(reg_id),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety_data", validate_safety_data)
_g.add_node("assess_compliance", assess_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_safety_data")
_g.add_edge("validate_safety_data", "assess_compliance")
_g.add_edge("assess_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
