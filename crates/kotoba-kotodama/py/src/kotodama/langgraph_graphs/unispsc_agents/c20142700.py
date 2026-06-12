# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142700 — Procurement (segment 20).

Bespoke graph logic for Procurement operations, validating requisitions,
verifying vendor compliance, and issuing purchase orders.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142700"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vendor_tier: str
    compliance_score: float
    purchase_order_id: str
    procurement_method: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition and sets method."""
    inp = state.get("input") or {}
    method = inp.get("method", "standard_tender")

    # Simple logic to determine compliance baseline
    compliance = 0.98 if "budget_code" in inp else 0.45

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "procurement_method": method,
        "compliance_score": compliance,
    }


def verify_vendor(state: State) -> dict[str, Any]:
    """Checks vendor status against the procurement method."""
    inp = state.get("input") or {}
    v_id = str(inp.get("vendor_id", "V-999"))

    # Assign tier based on mock vendor ID patterns
    tier = "preferred" if v_id.startswith("V-1") else "standard"

    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor"],
        "vendor_tier": tier,
    }


def authorize_and_issue(state: State) -> dict[str, Any]:
    """Authorizes the procurement and generates a transaction record."""
    v_tier = state.get("vendor_tier", "unknown")
    score = state.get("compliance_score", 0.0)
    method = state.get("procurement_method", "none")

    # Mock PO generation
    po_id = f"PO-{UNISPSC_CODE}-{abs(hash(v_tier + method)) % 100000}"
    is_ok = score > 0.5

    return {
        "log": [f"{UNISPSC_CODE}:authorize_and_issue"],
        "purchase_order_id": po_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "po_id": po_id,
            "status": "AUTHORIZED" if is_ok else "REJECTED",
            "vendor_tier": v_tier,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("verify", verify_vendor)
_g.add_node("issue", authorize_and_issue)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "issue")
_g.add_edge("issue", END)

graph = _g.compile()
