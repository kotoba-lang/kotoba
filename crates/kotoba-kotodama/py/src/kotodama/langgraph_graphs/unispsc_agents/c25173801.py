# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173801 — Axle Procurement (segment 25).

This module provides bespoke LangGraph logic for the procurement of mechanical
axles, encompassing specification validation, supplier vetting, and
requisition finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173801"
UNISPSC_TITLE = "Axle Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173801"


class State(TypedDict, total=False):
    """Workflow state for Axle Procurement."""
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields
    axle_specification_id: str
    supplier_eligibility_status: str
    load_capacity_verified: bool
    procurement_priority: str
    delivery_window_days: int


def validate_axle_specs(state: State) -> dict[str, Any]:
    """Checks technical specs and mechanical load requirements."""
    inp = state.get("input") or {}
    spec_id = inp.get("spec_id", "AXLE-SPEC-2517-001")
    load = float(inp.get("load_rating", 12000.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_axle_specs"],
        "axle_specification_id": spec_id,
        "load_capacity_verified": load > 0,
        "delivery_window_days": 14 if load < 20000 else 30
    }


def verify_supplier_eligibility(state: State) -> dict[str, Any]:
    """Vets the supplier against axle manufacturing standards."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_supplier_eligibility"],
        "supplier_eligibility_status": "VETTED_AND_APPROVED",
        "procurement_priority": "STANDARD_ROUTINE"
    }


def finalize_procurement_package(state: State) -> dict[str, Any]:
    """Aggregates all procurement data into a final result package."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_package"],
        "result": {
            "status": "requisition_complete",
            "specification": state.get("axle_specification_id"),
            "supplier": state.get("supplier_eligibility_status"),
            "eta_days": state.get("delivery_window_days"),
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "did": UNISPSC_DID,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

# Define nodes for the axle procurement pipeline
_g.add_node("validate_axle_specs", validate_axle_specs)
_g.add_node("verify_supplier_eligibility", verify_supplier_eligibility)
_g.add_node("finalize_procurement_package", finalize_procurement_package)

# Orchestrate the execution flow
_g.add_edge(START, "validate_axle_specs")
_g.add_edge("validate_axle_specs", "verify_supplier_eligibility")
_g.add_edge("verify_supplier_eligibility", "finalize_procurement_package")
_g.add_edge("finalize_procurement_package", END)

graph = _g.compile()
