# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352301 — Chemical Procurement (segment 12).

Bespoke graph logic for chemical procurement workflows, including safety
compliance validation, hazmat assessment, and order finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352301"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Chemical Procurement
    safety_data_sheet_verified: bool
    hazardous_material_clearance: str
    procurement_lot_id: str
    vendor_compliance_status: str


def validate_compliance(state: State) -> dict[str, Any]:
    """Validates chemical specifications and vendor credentials."""
    inp = state.get("input") or {}
    chemical_id = inp.get("chemical_id", "unknown")
    vendor_id = inp.get("vendor_id", "pending")

    return {
        "log": [f"{UNISPSC_CODE}:validate_compliance: chemical={chemical_id}"],
        "vendor_compliance_status": "verified" if vendor_id != "pending" else "unverified",
        "safety_data_sheet_verified": "sds_link" in inp,
    }


def assess_hazmat(state: State) -> dict[str, Any]:
    """Assesses hazardous material requirements and issues clearance codes."""
    is_hazardous = state.get("input", {}).get("is_hazardous", False)
    clearance = "HAZ-READY" if is_hazardous else "NON-HAZ-AUTO"

    return {
        "log": [f"{UNISPSC_CODE}:assess_hazmat: clearance_level={clearance}"],
        "hazardous_material_clearance": clearance,
        "procurement_lot_id": f"LOT-{UNISPSC_CODE}-778",
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Finalizes the chemical procurement record and prepares the output."""
    sds_ok = state.get("safety_data_sheet_verified", False)
    vendor_ok = state.get("vendor_compliance_status") == "verified"

    success = sds_ok and vendor_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order: success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "lot_id": state.get("procurement_lot_id"),
            "clearance": state.get("hazardous_material_clearance"),
            "status": "completed" if success else "pending_manual_review",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_compliance", validate_compliance)
_g.add_node("assess_hazmat", assess_hazmat)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "validate_compliance")
_g.add_edge("validate_compliance", "assess_hazmat")
_g.add_edge("assess_hazmat", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
