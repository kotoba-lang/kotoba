# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122619 — Procurement (segment 20).

This bespoke implementation handles procurement workflows for mining and
well drilling services, focusing on requisition validation, vendor
sourcing, and purchase order finalization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122619"
UNISPSC_TITLE = "Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122619"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Procurement
    requisition_id: str
    total_cost: float
    vendor_shortlist: list[str]
    compliance_passed: bool


def validate_requisition(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request and budget availability."""
    inp = state.get("input") or {}
    req_id = inp.get("requisition_id", "REQ-UNKN-001")
    cost = float(inp.get("estimated_cost", 0.0))

    # In a real scenario, this would check against departmental budgets
    is_valid = cost > 0 and "items" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_requisition"],
        "requisition_id": req_id,
        "total_cost": cost,
        "compliance_passed": is_valid
    }


def source_vendors(state: State) -> dict[str, Any]:
    """Identifies approved vendors capable of fulfilling the drilling service reqs."""
    if not state.get("compliance_passed"):
        return {"log": [f"{UNISPSC_CODE}:source_vendors:skipped"]}

    # Mocking vendor selection logic for drilling machinery and services
    vendors = ["DeepCore Drilling Ltd", "GeoResources Supply", "Titan Mining Services"]
    return {
        "log": [f"{UNISPSC_CODE}:source_vendors"],
        "vendor_shortlist": vendors
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the procurement result or rejection notice."""
    success = state.get("compliance_passed", False)
    vendors = state.get("vendor_shortlist", [])
    selected = vendors[0] if vendors else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "requisition_id": state.get("requisition_id"),
            "status": "APPROVED" if success else "REJECTED",
            "selected_vendor": selected,
            "total_value": state.get("total_cost", 0.0),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_requisition", validate_requisition)
_g.add_node("source_vendors", source_vendors)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_requisition")
_g.add_edge("validate_requisition", "source_vendors")
_g.add_edge("source_vendors", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
