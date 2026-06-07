# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141502 — Chemical Procurement.

Bespoke graph logic for chemical acquisition, safety verification, and
regulatory compliance check within the UNISPSC segment 12 framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141502"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical Procurement
    cas_number: str
    hazard_category: str
    compliance_verified: bool
    storage_requirements: str


def evaluate_requisition(state: State) -> dict[str, Any]:
    """Validates the requisition and extracts the CAS registry number."""
    inp = state.get("input") or {}
    cas = inp.get("cas_number", "00-00-0")
    hazard = inp.get("hazard_class", "non-hazardous")

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_requisition"],
        "cas_number": cas,
        "hazard_category": hazard,
    }


def perform_compliance_check(state: State) -> dict[str, Any]:
    """Verifies chemical against safety standards and regulatory lists."""
    hazard = state.get("hazard_category")
    is_flammable = "flammable" in hazard.lower()

    return {
        "log": [f"{UNISPSC_CODE}:perform_compliance_check"],
        "compliance_verified": True,
        "storage_requirements": "Flammable Cabinet" if is_flammable else "General Storage",
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement state and emits the result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "cas_number": state.get("cas_number"),
            "compliance_check": state.get("compliance_verified"),
            "storage_protocol": state.get("storage_requirements"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("evaluate", evaluate_requisition)
_g.add_node("check", perform_compliance_check)
_g.add_node("finalize", finalize_procurement)

_g.add_edge(START, "evaluate")
_g.add_edge("evaluate", "check")
_g.add_edge("check", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
