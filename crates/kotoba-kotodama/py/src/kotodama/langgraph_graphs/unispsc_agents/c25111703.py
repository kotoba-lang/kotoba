# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111703 — Ship Procurement (segment 25).

This bespoke graph manages the procurement lifecycle for maritime vessels,
handling specification validation, vendor assessment, and final issuance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111703"
UNISPSC_TITLE = "Ship Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vessel_class: str
    specs_verified: bool
    vendor_id: str
    budget_authorized: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Verify maritime specifications and vessel class."""
    inp = state.get("input") or {}
    v_class = inp.get("vessel_class", "unspecified")
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "vessel_class": v_class,
        "specs_verified": True if v_class != "unspecified" else False,
    }


def assess_vendor(state: State) -> dict[str, Any]:
    """Check vendor certification for ship building or brokerage."""
    inp = state.get("input") or {}
    v_id = inp.get("vendor_id", "V-PENDING")
    return {
        "log": [f"{UNISPSC_CODE}:assess_vendor"],
        "vendor_id": v_id,
        "budget_authorized": state.get("specs_verified", False),
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Emit the final procurement status."""
    success = state.get("specs_verified", False) and state.get("budget_authorized", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vessel_class": state.get("vessel_class"),
            "vendor_id": state.get("vendor_id"),
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("assess_vendor", assess_vendor)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "assess_vendor")
_g.add_edge("assess_vendor", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
