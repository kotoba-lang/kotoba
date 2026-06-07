# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173900"
UNISPSC_TITLE = "Procure"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    requisition_valid: bool
    selected_vendor: str
    purchase_order_id: str
    allocation_confirmed: bool


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement requisition for vehicle components."""
    inp = state.get("input") or {}
    item_id = inp.get("item_id")
    quantity = inp.get("quantity", 0)
    is_valid = bool(item_id and quantity > 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_valid": is_valid
    }


def source_vendor(state: State) -> dict[str, Any]:
    """Identifies and selects a suitable vendor for the requested parts."""
    if not state.get("requisition_valid"):
        return {"log": [f"{UNISPSC_CODE}:source_vendor_skipped"]}

    inp = state.get("input") or {}
    preferred = inp.get("preferred_vendor", "Global Transit Systems Ltd")

    return {
        "log": [f"{UNISPSC_CODE}:source_vendor"],
        "selected_vendor": preferred
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Generates the purchase order and confirms inventory allocation."""
    vendor = state.get("selected_vendor")
    if not vendor:
        return {
            "log": [f"{UNISPSC_CODE}:execute_procurement_failed"],
            "result": {"ok": False, "error": "Procurement aborted: invalid source"}
        }

    po_id = f"PO-{UNISPSC_CODE}-9988"

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "purchase_order_id": po_id,
        "allocation_confirmed": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "po_id": po_id,
            "vendor": vendor,
            "status": "issued",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requisition)
_g.add_node("source", source_vendor)
_g.add_node("execute", execute_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "source")
_g.add_edge("source", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
