# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101210 — Motor Procurement (segment 26).

This bespoke implementation handles motor procurement workflows, including
vendor sourcing validation, lead time estimation, and unit cost verification
against market benchmarks.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101210"
UNISPSC_TITLE = "Motor Procurement"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101210"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Motor Procurement
    vendor_verified: bool
    lead_time_weeks: int
    quote_currency: str
    unit_cost_score: float


def verify_vendor_credentials(state: State) -> dict[str, Any]:
    """Verify the vendor is authorized for electrical motor procurement."""
    inp = state.get("input") or {}
    vendor_id = inp.get("vendor_id", "UNKNOWN")

    # Simulate verification logic: codes starting with VEN-26 are motor-specialized
    is_authorized = vendor_id.startswith("VEN-26")
    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_credentials"],
        "vendor_verified": is_authorized,
        "quote_currency": inp.get("currency", "USD"),
    }


def analyze_procurement_terms(state: State) -> dict[str, Any]:
    """Analyze delivery timelines and cost efficiency."""
    inp = state.get("input") or {}
    quantity = inp.get("quantity", 1)
    urgency = inp.get("urgency", "standard")

    lead_time = 4 if urgency == "express" else 12
    # Simple heuristic for cost score: volume discounts apply above 10 units
    cost_score = 0.95 if quantity > 10 else 0.80

    return {
        "log": [f"{UNISPSC_CODE}:analyze_procurement_terms"],
        "lead_time_weeks": lead_time,
        "unit_cost_score": cost_score,
    }


def emit_procurement_summary(state: State) -> dict[str, Any]:
    """Generate the final procurement actor declaration."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_procurement_summary"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ready" if state.get("vendor_verified") else "pending_verification",
            "procurement_data": {
                "vendor_ok": state.get("vendor_verified"),
                "lead_time": f"{state.get('lead_time_weeks')} weeks",
                "efficiency_rating": state.get("unit_cost_score"),
                "currency": state.get("quote_currency"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("verify_vendor_credentials", verify_vendor_credentials)
_g.add_node("analyze_procurement_terms", analyze_procurement_terms)
_g.add_node("emit_procurement_summary", emit_procurement_summary)

_g.add_edge(START, "verify_vendor_credentials")
_g.add_edge("verify_vendor_credentials", "analyze_procurement_terms")
_g.add_edge("analyze_procurement_terms", "emit_procurement_summary")
_g.add_edge("emit_procurement_summary", END)

graph = _g.compile()
