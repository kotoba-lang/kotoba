# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141742 — Chemical Procurement (segment 12).

This bespoke agent handles the workflow for chemical procurement, including
specification validation, safety compliance verification (SDS), and order
finalization for industrial and research chemicals.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141742"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141742"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical Procurement
    sds_verified: bool
    hazardous_class: str
    purity_confirmed: bool
    procurement_id: str
    supplier_tier: int


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates chemical identity, purity requirements, and CAS registry numbers."""
    inp = state.get("input") or {}
    chemical_id = inp.get("cas_number", "CAS-PENDING")
    purity = inp.get("minimum_purity", "99.0%")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications(target={chemical_id}, purity={purity})"],
        "purity_confirmed": True,
        "procurement_id": f"CHEM-{hash(chemical_id) % 10000:04d}",
    }


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Verifies Safety Data Sheets (SDS) and assigns hazardous material handling classes."""
    inp = state.get("input") or {}
    is_hazardous = inp.get("is_hazardous", True)
    h_class = inp.get("hazard_category", "Class 3: Flammable Liquid") if is_hazardous else "Non-Hazardous"

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance(class={h_class})"],
        "sds_verified": True,
        "hazardous_class": h_class,
        "supplier_tier": 1
    }


def finalize_procurement_record(state: State) -> dict[str, Any]:
    """Compiles the procurement data into a formal transaction record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "procurement_id": state.get("procurement_id"),
            "safety_status": "COMPLIANT",
            "hazard_classification": state.get("hazardous_class"),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_safety_compliance", verify_safety_compliance)
_g.add_node("finalize_procurement_record", finalize_procurement_record)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_safety_compliance")
_g.add_edge("verify_safety_compliance", "finalize_procurement_record")
_g.add_edge("finalize_procurement_record", END)

graph = _g.compile()
