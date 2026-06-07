# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131300"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke procurement domain state
    requisition_id: str
    vendor_selection: str
    approval_workflow_id: str
    total_estimated_value: float


def review_requisition(state: State) -> dict[str, Any]:
    """Analyzes the initial procurement request and assigns a requisition tracking ID."""
    inp = state.get("input") or {}
    req_id = inp.get("req_id", f"REQ-{UNISPSC_CODE}-55")
    value = float(inp.get("value", 1250.0))

    return {
        "log": [f"{UNISPSC_CODE}:review_requisition"],
        "requisition_id": req_id,
        "total_estimated_value": value,
        "approval_workflow_id": "WF-PROC-STANDARD"
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Selects the optimal vendor source based on the requisition value and policy."""
    value = state.get("total_estimated_value", 0.0)
    # High value items trigger strategic sourcing; lower values use catalog vendors
    selection = "STRATEGIC-PARTNER" if value > 10000 else "PREFERRED-CATALOG-V1"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_selection": selection
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Wraps up the procurement process and emits the final authorization record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "selected_vendor": state.get("vendor_selection"),
            "estimated_value": state.get("total_estimated_value"),
            "workflow": state.get("approval_workflow_id"),
            "status": "AUTHORIZED",
            "ok": True
        }
    }


_g = StateGraph(State)

_g.add_node("review", review_requisition)
_g.add_node("evaluate", evaluate_vendors)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "review")
_g.add_edge("review", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
