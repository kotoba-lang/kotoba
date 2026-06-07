# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111602 — Gold Procurement (segment 11).

Bespoke LangGraph implementation for Gold Procurement. This agent handles
the verification of gold purity, valuation against market spot prices,
and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111602"
UNISPSC_TITLE = "Gold Procurement"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Gold Procurement
    purity_grade: float
    weight_oz: float
    assay_verified: bool
    valuation_usd: float


def verify_assay(state: State) -> dict[str, Any]:
    """Verify the gold's purity and weight from the input metadata."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)
    weight = inp.get("weight", 0.0)

    # Simple logic: verify if purity is at least 0.995 (standard for London Good Delivery)
    verified = purity >= 0.995

    return {
        "log": [f"{UNISPSC_CODE}:verify_assay - Purity: {purity}, Weight: {weight}, Verified: {verified}"],
        "purity_grade": purity,
        "weight_oz": weight,
        "assay_verified": verified,
    }


def calculate_valuation(state: State) -> dict[str, Any]:
    """Calculate the current market valuation of the procurement lot."""
    inp = state.get("input") or {}
    spot_price = inp.get("spot_price", 2000.0)  # Default/Placeholder spot price
    weight = state.get("weight_oz", 0.0)

    # Only value if assay is verified
    valuation = weight * spot_price if state.get("assay_verified") else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_valuation - Spot Price: {spot_price}, Total: {valuation}"],
        "valuation_usd": valuation,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement record and emit the result."""
    verified = state.get("assay_verified", False)
    valuation = state.get("valuation_usd", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement - Success: {verified}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verified": verified,
            "valuation": valuation,
            "currency": "USD",
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_assay", verify_assay)
_g.add_node("calculate_valuation", calculate_valuation)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "verify_assay")
_g.add_edge("verify_assay", "calculate_valuation")
_g.add_edge("calculate_valuation", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
