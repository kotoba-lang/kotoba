# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121605 — Tram Procurement (segment 25).

Bespoke logic for managing the procurement lifecycle of tramway vehicles,
including specification review, vendor vetting, and budget alignment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121605"
UNISPSC_TITLE = "Tram Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Tram Procurement
    technical_specs: dict[str, Any]
    vendor_qualified: bool
    budget_approved: bool
    procurement_id: str


def review_specifications(state: State) -> dict[str, Any]:
    """Evaluates the technical requirements for the tram vehicle."""
    inp = state.get("input", {})
    specs = inp.get("specs", {})
    # Mock validation of rail gauge and passenger capacity
    valid_specs = specs.get("gauge_mm") == 1435 and specs.get("capacity", 0) > 50
    return {
        "log": [f"{UNISPSC_CODE}:review_specifications:valid={valid_specs}"],
        "technical_specs": specs,
        "budget_approved": specs.get("cost_estimate", 0) < 5000000,
    }


def vet_vendors(state: State) -> dict[str, Any]:
    """Verifies that the proposed vendor is qualified for municipal transport."""
    inp = state.get("input", {})
    vendor_name = inp.get("vendor", "unknown")
    # Logic: Qualified if the vendor is a known manufacturer in the input
    is_qualified = vendor_name in ["Alstom", "Siemens", "Bombardier", "Stadler"]
    return {
        "log": [f"{UNISPSC_CODE}:vet_vendors:qualified={is_qualified}"],
        "vendor_qualified": is_qualified,
        "procurement_id": f"TRAM-PRC-{UNISPSC_CODE}-{hash(vendor_name) % 10000:04d}",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Consolidates the procurement state into a final decision record."""
    qualified = state.get("vendor_qualified", False)
    budgeted = state.get("budget_approved", False)
    is_ok = qualified and budgeted

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement:ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "APPROVED" if is_ok else "REJECTED",
            "reasoning": "Vendor and budget criteria met" if is_ok else "Criteria failure",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("review_specifications", review_specifications)
_g.add_node("vet_vendors", vet_vendors)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "review_specifications")
_g.add_edge("review_specifications", "vet_vendors")
_g.add_edge("vet_vendors", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
