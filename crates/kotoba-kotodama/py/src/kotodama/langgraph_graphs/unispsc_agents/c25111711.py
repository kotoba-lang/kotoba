# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111711 — Ship Procurement (segment 25).

Bespoke logic for handling ship procurement processes, including requirement
assessment, vendor evaluation, and finalization of procurement records.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111711"
UNISPSC_TITLE = "Ship Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111711"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Ship Procurement
    vessel_class: str
    procurement_id: str
    vendor_shortlist: list[str]
    compliance_approved: bool


def assess_requirements(state: State) -> dict[str, Any]:
    """Analyze input to determine the vessel requirements and procurement ID."""
    inp = state.get("input") or {}
    vessel_class = inp.get("vessel_class", "Standard Transport")
    procurement_id = inp.get("procurement_id", "SP-25-DEFAULT")
    return {
        "log": [f"{UNISPSC_CODE}:assess_requirements"],
        "vessel_class": vessel_class,
        "procurement_id": procurement_id,
        "compliance_approved": False,
    }


def evaluate_vendors(state: State) -> dict[str, Any]:
    """Mock evaluation of potential shipbuilders or maritime vendors."""
    vessel_class = state.get("vessel_class", "Unknown")
    # Simulation of vendor matching based on vessel class
    if "Standard" in vessel_class:
        vendors = ["Global Maritime", "Oceanic Logistics"]
    else:
        vendors = ["Specialized Marine Systems", "Custom Hull Works"]

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_vendors"],
        "vendor_shortlist": vendors,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Wrap up the procurement state and emit the final record."""
    vendors = state.get("vendor_shortlist") or []
    primary_vendor = vendors[0] if vendors else "N/A"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "compliance_approved": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "vessel_class": state.get("vessel_class"),
            "procurement_id": state.get("procurement_id"),
            "assigned_vendor": primary_vendor,
            "status": "PROCUREMENT_INITIATED",
        },
    }


_g = StateGraph(State)
_g.add_node("assess_requirements", assess_requirements)
_g.add_node("evaluate_vendors", evaluate_vendors)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "assess_requirements")
_g.add_edge("assess_requirements", "evaluate_vendors")
_g.add_edge("evaluate_vendors", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
