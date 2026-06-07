# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181604 — Press Procurement.

This bespoke graph manages the procurement lifecycle for industrial press machinery,
including requirement validation, vendor sourcing simulations, and contract finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181604"
UNISPSC_TITLE = "Press Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Press Procurement
    press_specs: dict[str, Any]
    vendor_shortlist: list[str]
    budget_approved: bool
    procurement_phase: str


def assess_requirements(state: State) -> dict[str, Any]:
    """Analyzes the input for press specifications and budget constraints."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {"type": "industrial_offset", "tonnage": 500})
    budget = inp.get("budget", 0)

    return {
        "log": [f"{UNISPSC_CODE}:assess_requirements"],
        "press_specs": specs,
        "budget_approved": budget > 10000,
        "procurement_phase": "initial_assessment"
    }


def source_vendors(state: State) -> dict[str, Any]:
    """Identifies potential suppliers based on equipment specifications."""
    specs = state.get("press_specs", {})
    press_type = specs.get("type", "standard")

    # Simulated vendor matching logic
    vendors = ["GlobalPress Corp", "Precision Machinery Ltd"]
    if specs.get("tonnage", 0) > 1000:
        vendors.append("HeavyLift Industrials")

    return {
        "log": [f"{UNISPSC_CODE}:source_vendors"],
        "vendor_shortlist": vendors,
        "procurement_phase": "vendor_sourcing"
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Consolidates the procurement plan and emits the final result."""
    approved = state.get("budget_approved", False)
    vendors = state.get("vendor_shortlist", [])

    status = "ready_for_tender" if approved and vendors else "rejected"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "procurement_phase": "finalized",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": status,
            "selected_vendors": vendors,
            "ok": approved and len(vendors) > 0,
            "did": UNISPSC_DID
        }
    }


_g = StateGraph(State)

_g.add_node("assess_requirements", assess_requirements)
_g.add_node("source_vendors", source_vendors)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "assess_requirements")
_g.add_edge("assess_requirements", "source_vendors")
_g.add_edge("source_vendors", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
