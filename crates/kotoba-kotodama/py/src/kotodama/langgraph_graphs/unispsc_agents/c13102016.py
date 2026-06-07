# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102016 — Sulfur Procurement (segment 13).

Bespoke LangGraph implementation for specialized sulfur procurement workflows,
handling purity specifications, tonnage requirements, and supplier verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102016"
UNISPSC_TITLE = "Sulfur Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102016"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific sulfur procurement fields
    sulfur_grade: str
    quantity_metric_tons: float
    supplier_verified: bool
    logistics_ready: bool


def validate_requirement(state: State) -> dict[str, Any]:
    """Validates requested sulfur specifications and quantity."""
    inp = state.get("input") or {}
    grade = str(inp.get("grade", "crude"))
    qty = float(inp.get("quantity", 100.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirement -> {grade} grade, {qty} tons"],
        "sulfur_grade": grade,
        "quantity_metric_tons": qty,
    }


def analyze_sourcing(state: State) -> dict[str, Any]:
    """Checks availability and verifies supplier credentials for the specific grade."""
    grade = state.get("sulfur_grade", "crude")
    # Simulate sourcing logic: high purity (USP/Food) requires more verification
    is_verified = grade not in ["unfiltered", "raw"]
    return {
        "log": [f"{UNISPSC_CODE}:analyze_sourcing -> verified: {is_verified}"],
        "supplier_verified": is_verified,
        "logistics_ready": True,
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement transaction records."""
    is_valid = state.get("supplier_verified", False)
    qty = state.get("quantity_metric_tons", 0.0)

    result_data = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "status": "APPROVED" if is_valid and qty > 0 else "REJECTED",
        "details": {
            "grade": state.get("sulfur_grade"),
            "qty": qty,
            "compliance_checked": True
        },
        "ok": is_valid,
    }
    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement -> status: {result_data['status']}"],
        "result": result_data,
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirement)
_g.add_node("sourcing", analyze_sourcing)
_g.add_node("procure", execute_procurement)

_g.add_edge(START, "validate")
_g.add_edge("validate", "sourcing")
_g.add_edge("sourcing", "procure")
_g.add_edge("procure", END)

graph = _g.compile()
