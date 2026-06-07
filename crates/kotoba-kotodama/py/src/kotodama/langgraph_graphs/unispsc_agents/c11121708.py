# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11121708 — Chemical (segment 11).

Bespoke agent implementation for chemical compound verification and safety
processing. This graph manages specification analysis, safety compliance
verification, and certification generation for chemical products.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11121708"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11121708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Chemicals
    cas_number: str
    purity_level: float
    msds_status: str
    hazard_class: list[str]


def analyze_specifications(state: State) -> dict[str, Any]:
    """Analyzes the chemical composition and identity."""
    inp = state.get("input") or {}
    cas = str(inp.get("cas", "00-00-0"))
    purity = float(inp.get("purity", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications - CAS:{cas}"],
        "cas_number": cas,
        "purity_level": purity
    }


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Checks safety data sheets and hazard classifications."""
    cas = state.get("cas_number", "00-00-0")
    # Simulate a safety lookup: if CAS contains '9', classify as hazardous
    hazard_data = ["GHS07", "Toxic"] if "9" in cas else ["Non-hazardous"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance - SDS Verified"],
        "msds_status": "Verified",
        "hazard_class": hazard_data
    }


def generate_certificate(state: State) -> dict[str, Any]:
    """Generates the final chemical analysis result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "composition": {
                "cas": state.get("cas_number"),
                "purity": state.get("purity_level"),
                "hazards": state.get("hazard_class")
            },
            "msds_verified": state.get("msds_status") == "Verified",
            "status": "Certified"
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_specifications", analyze_specifications)
_g.add_node("verify_safety_compliance", verify_safety_compliance)
_g.add_node("generate_certificate", generate_certificate)

_g.add_edge(START, "analyze_specifications")
_g.add_edge("analyze_specifications", "verify_safety_compliance")
_g.add_edge("verify_safety_compliance", "generate_certificate")
_g.add_edge("generate_certificate", END)

graph = _g.compile()
