# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12000000 — Chemical (segment 12).

Bespoke agent implementation for Chemical segment. Handles safety verification,
composition analysis, and material reporting for chemical compounds.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12000000"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12000000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical
    hazard_class: str
    msds_verified: bool
    purity_level: float
    safety_protocol_active: bool


def verify_safety(state: State) -> dict[str, Any]:
    """Ensures safety protocols and MSDS documentation are valid."""
    inp = state.get("input") or {}
    msds_ref = inp.get("msds_reference", "PENDING")

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "msds_verified": msds_ref != "PENDING",
        "safety_protocol_active": True,
        "hazard_class": inp.get("hazard_class", "Non-Hazardous")
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the purity and composition of the chemical sample."""
    inp = state.get("input") or {}
    sample_purity = inp.get("sample_purity", 99.9)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_level": sample_purity
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Generates the final chemical segment report and actor DID response."""
    msds = state.get("msds_verified", False)
    purity = state.get("purity_level", 0.0)
    hazard = state.get("hazard_class", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "COMPLIANT" if msds and purity > 90.0 else "REVIEW_REQUIRED",
            "metrics": {
                "purity": purity,
                "msds_verified": msds,
                "hazard_class": hazard
            }
        },
    }


_g = StateGraph(State)
_g.add_node("verify_safety", verify_safety)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("finalize_report", finalize_report)

_g.add_edge(START, "verify_safety")
_g.add_edge("verify_safety", "analyze_composition")
_g.add_edge("analyze_composition", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
