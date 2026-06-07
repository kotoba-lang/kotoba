# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111720 — Ship Procurement (segment 25).
Bespoke logic for handling vessel acquisition and maritime procurement workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111720"
UNISPSC_TITLE = "Ship Procurement"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111720"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Ship Procurement
    vessel_class: str
    deadweight_tonnage: int
    procurement_status: str
    certified_vendors: list[str]


def assess_requirements(state: State) -> dict[str, Any]:
    """Assess vessel requirements and specify vessel class based on input."""
    inp = state.get("input") or {}
    v_class = inp.get("vessel_class", "General Cargo")
    dwt = inp.get("dwt", 5000)
    return {
        "log": [f"{UNISPSC_CODE}:assess_requirements"],
        "vessel_class": v_class,
        "deadweight_tonnage": dwt,
        "procurement_status": "Requirements Defined",
    }


def verify_vendors(state: State) -> dict[str, Any]:
    """Verify shipyard capacity and shortlist certified maritime vendors."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_vendors"],
        "certified_vendors": ["Global Shipyards Inc.", "DeepSea Engineering", "Vertex Marine"],
        "procurement_status": "Vendors Verified",
    }


def execute_procurement(state: State) -> dict[str, Any]:
    """Finalize the procurement request for the specified ship acquisition."""
    v_class = state.get("vessel_class")
    dwt = state.get("deadweight_tonnage")
    status = state.get("procurement_status")

    return {
        "log": [f"{UNISPSC_CODE}:execute_procurement"],
        "procurement_status": "Execution Ready",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel_class": v_class,
            "tonnage": dwt,
            "workflow_last_status": status,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_requirements", assess_requirements)
_g.add_node("verify_vendors", verify_vendors)
_g.add_node("execute_procurement", execute_procurement)

_g.add_edge(START, "assess_requirements")
_g.add_edge("assess_requirements", "verify_vendors")
_g.add_edge("verify_vendors", "execute_procurement")
_g.add_edge("execute_procurement", END)

graph = _g.compile()
