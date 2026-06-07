# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101700 — Vehicle Procurement (segment 25).

Bespoke LangGraph implementation for vehicle procurement processes,
handling requirement gathering, vendor vetting, and record finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101700"
UNISPSC_TITLE = "Vehicle Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain state for Vehicle Procurement
    procurement_id: str
    vehicle_type: str
    vendor_lead_id: str
    safety_audit_passed: bool


def analyze_procurement_request(state: State) -> dict[str, Any]:
    """Analyzes the incoming request and assigns a procurement tracking ID."""
    inp = state.get("input") or {}
    v_type = inp.get("vehicle_type", "commercial_standard")
    p_id = f"PROC-{UNISPSC_CODE}-{v_type[:3].upper()}"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_procurement_request"],
        "procurement_id": p_id,
        "vehicle_type": v_type,
    }


def perform_vendor_vetting(state: State) -> dict[str, Any]:
    """Simulates the selection and verification of a vehicle vendor."""
    return {
        "log": [f"{UNISPSC_CODE}:perform_vendor_vetting"],
        "vendor_lead_id": "V-L-99812",
        "safety_audit_passed": True,
    }


def generate_procurement_result(state: State) -> dict[str, Any]:
    """Constructs the final procurement artifact for the actor."""
    p_id = state.get("procurement_id", "PENDING")
    v_type = state.get("vehicle_type", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:generate_procurement_result"],
        "result": {
            "procurement_id": p_id,
            "vehicle_type": v_type,
            "status": "authorized",
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "did": UNISPSC_DID,
            },
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_procurement_request", analyze_procurement_request)
_g.add_node("perform_vendor_vetting", perform_vendor_vetting)
_g.add_node("generate_procurement_result", generate_procurement_result)

_g.add_edge(START, "analyze_procurement_request")
_g.add_edge("analyze_procurement_request", "perform_vendor_vetting")
_g.add_edge("perform_vendor_vetting", "generate_procurement_result")
_g.add_edge("generate_procurement_result", END)

graph = _g.compile()
