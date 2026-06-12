# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10122001"
UNISPSC_TITLE = "Feed Procurement"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10122001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    procurement_id: str
    feed_type: str
    quantity_tons: float
    vendor_verified: bool
    compliance_score: float


def analyze_request(state: State) -> dict[str, Any]:
    """Analyzes the initial procurement request and extracts core specifications."""
    inp = state.get("input") or {}
    f_type = str(inp.get("feed_type", "standard_forage"))
    qty = float(inp.get("quantity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_request"],
        "feed_type": f_type,
        "quantity_tons": qty,
        "procurement_id": f"FP-{UNISPSC_CODE}-{abs(hash(f_type + str(qty))) % 10000:04d}"
    }


def verify_vendor_compliance(state: State) -> dict[str, Any]:
    """Simulates checking vendor certification against Segment 10 agricultural standards."""
    qty = state.get("quantity_tons", 0.0)
    # Basic logic: ensure quantity is within handled limits and type is recognized
    is_valid = qty > 0 and state.get("feed_type") != "unspecified"

    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_compliance"],
        "vendor_verified": is_valid,
        "compliance_score": 0.98 if is_valid else 0.0
    }


def finalize_procurement_record(state: State) -> dict[str, Any]:
    """Constructs the final procurement result based on verification outcomes."""
    verified = state.get("vendor_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_id": state.get("procurement_id"),
            "status": "APPROVED" if verified else "REJECTED",
            "details": {
                "feed": state.get("feed_type"),
                "tonnage": state.get("quantity_tons"),
                "compliance": state.get("compliance_score")
            },
            "ok": verified
        }
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_request)
_g.add_node("verify", verify_vendor_compliance)
_g.add_node("finalize", finalize_procurement_record)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
