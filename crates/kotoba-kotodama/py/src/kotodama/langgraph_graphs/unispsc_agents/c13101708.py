# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13101708 — Chemical Procurement (segment 13).

This module implements bespoke logic for chemical acquisition, including
safety verification and regulatory hazmat checks for segment 13.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101708"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Chemical Procurement
    requisition_items: list[str]
    sds_verified: bool
    hazmat_class: str
    procurement_status: str


def validate_requisition(state: State) -> dict[str, Any]:
    """Analyzes incoming request for chemical items and quantities."""
    inp = state.get("input") or {}
    items = inp.get("items", ["industrial-reagent-a1"])
    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_items": items,
    }


def check_hazmat_compliance(state: State) -> dict[str, Any]:
    """Simulates checking Safety Data Sheets (SDS) and Hazmat regulations."""
    items = state.get("requisition_items") or []
    # Simple logic: ensure items do not contain forbidden keywords
    is_safe = all("forbidden" not in item.lower() for item in items)
    return {
        "log": [f"{UNISPSC_CODE}:check_hazmat_compliance"],
        "sds_verified": is_safe,
        "hazmat_class": "Class 3 Flammable" if is_safe else "UNAUTHORIZED",
    }


def finalize_order(state: State) -> dict[str, Any]:
    """Completes the procurement process or marks it for manual review."""
    sds_ok = state.get("sds_verified", False)
    status = "Ordered" if sds_ok else "Rejected-Regulatory-Hold"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_order"],
        "procurement_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": status,
            "hazmat_class": state.get("hazmat_class"),
            "ok": sds_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("check_hazmat_compliance", check_hazmat_compliance)
_g.add_node("finalize_order", finalize_order)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "check_hazmat_compliance")
_g.add_edge("check_hazmat_compliance", "finalize_order")
_g.add_edge("finalize_order", END)

graph = _g.compile()
