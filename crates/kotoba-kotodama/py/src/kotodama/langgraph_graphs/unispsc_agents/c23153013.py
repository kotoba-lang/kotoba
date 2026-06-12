# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153013 — Motion Procurement (segment 23).

Bespoke LangGraph implementation for Motion Procurement. This agent manages
the procurement lifecycle for motion control systems and industrial components,
ensuring technical specifications meet manufacturing standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153013"
UNISPSC_TITLE = "Motion Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153013"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Motion Procurement
    specification_id: str
    vendor_shortlist: list[str]
    budget_verified: bool
    procurement_status: str


def analyze_requirements(state: State) -> dict[str, Any]:
    """Analyzes motion control requirements and extracts technical specs."""
    inp = state.get("input") or {}
    spec_id = inp.get("spec_id", "MOT-DEFAULT-001")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_requirements"],
        "specification_id": spec_id,
        "procurement_status": "analyzing",
    }


def source_vendors(state: State) -> dict[str, Any]:
    """Identifies qualified vendors for the specific motion control hardware."""
    # Logic to filter vendors based on specification_id
    vendors = ["PrecisionMotion Inc.", "IndustrialDynamics", "ServoFlow Systems"]
    return {
        "log": [f"{UNISPSC_CODE}:source_vendors"],
        "vendor_shortlist": vendors,
        "procurement_status": "sourcing",
    }


def verify_and_authorize(state: State) -> dict[str, Any]:
    """Verifies budget allocation and authorizes the procurement request."""
    inp = state.get("input") or {}
    budget = inp.get("budget", 0)
    authorized = budget > 5000  # Example threshold for motion systems

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_authorize"],
        "budget_verified": authorized,
        "procurement_status": "authorized" if authorized else "rejected",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification_id": state.get("specification_id"),
            "authorized": authorized,
            "ok": authorized,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_requirements", analyze_requirements)
_g.add_node("source_vendors", source_vendors)
_g.add_node("verify_and_authorize", verify_and_authorize)

_g.add_edge(START, "analyze_requirements")
_g.add_edge("analyze_requirements", "source_vendors")
_g.add_edge("source_vendors", "verify_and_authorize")
_g.add_edge("verify_and_authorize", END)

graph = _g.compile()
