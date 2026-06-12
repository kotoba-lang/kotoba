# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11161704 — Chemical Procurement (segment 11).

Bespoke graph logic for chemical procurement workflows, including
safety data sheet verification and hazardous material compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11161704"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11161704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical Procurement
    msds_verified: bool
    hazmat_classification: str
    supplier_compliance_status: str
    procurement_tracking_id: str


def validate_safety_compliance(state: State) -> dict[str, Any]:
    """Verify Material Safety Data Sheet (MSDS) and hazardous classification."""
    inp = state.get("input") or {}
    chemical_name = inp.get("chemical_name", "Standard Reagent")
    msds_exists = inp.get("has_msds", False)
    haz_class = inp.get("hazmat_class", "Class 3 - Flammable")

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_compliance - Chemical: {chemical_name}"],
        "msds_verified": msds_exists,
        "hazmat_classification": haz_class,
    }


def assess_procurement_risk(state: State) -> dict[str, Any]:
    """Evaluate supplier compliance and assign a procurement tracking ID."""
    msds_ok = state.get("msds_verified", False)
    status = "Approved" if msds_ok else "Documentation Required"
    track_id = f"CHM-PRC-{UNISPSC_CODE}-77"

    return {
        "log": [f"{UNISPSC_CODE}:assess_procurement_risk - Status: {status}"],
        "supplier_compliance_status": status,
        "procurement_tracking_id": track_id,
    }


def emit_procurement_record(state: State) -> dict[str, Any]:
    """Finalize the procurement record and emit the result."""
    is_ok = state.get("msds_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_procurement_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "tracking_id": state.get("procurement_tracking_id"),
            "compliance_status": state.get("supplier_compliance_status"),
            "hazmat_class": state.get("hazmat_classification"),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety_compliance", validate_safety_compliance)
_g.add_node("assess_procurement_risk", assess_procurement_risk)
_g.add_node("emit_procurement_record", emit_procurement_record)

_g.add_edge(START, "validate_safety_compliance")
_g.add_edge("validate_safety_compliance", "assess_procurement_risk")
_g.add_edge("assess_procurement_risk", "emit_procurement_record")
_g.add_edge("emit_procurement_record", END)

graph = _g.compile()
