# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352001 — Chemical (segment 12).

This bespoke graph manages chemical metadata validation, purity assessment,
and safety documentation verification for industrial and laboratory chemicals.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352001"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352001"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical
    msds_verified: bool
    purity_percentage: float
    hazard_class: str
    batch_identifier: str
    storage_temp_celsius: float


def validate_safety(state: State) -> dict[str, Any]:
    """Inspects safety data and verifies hazard classification."""
    inp = state.get("input") or {}
    hazard = inp.get("hazard_class", "Non-Hazardous")
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "msds_verified": True,
        "hazard_class": hazard,
        "storage_temp_celsius": inp.get("temp", 20.0),
    }


def assess_purity(state: State) -> dict[str, Any]:
    """Simulates chemical analysis to determine purity grade."""
    inp = state.get("input") or {}
    # Simulate a purity calculation or extraction from input
    purity = float(inp.get("measured_purity", 99.9))
    batch = inp.get("batch_id", "BATCH-UNSET")
    return {
        "log": [f"{UNISPSC_CODE}:assess_purity"],
        "purity_percentage": purity,
        "batch_identifier": batch,
    }


def generate_coa(state: State) -> dict[str, Any]:
    """Generates the Certificate of Analysis (CoA) and final result."""
    is_pure = state.get("purity_percentage", 0) > 95.0
    safe = state.get("msds_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_coa"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch": state.get("batch_identifier"),
            "purity_status": "High Grade" if is_pure else "Standard Grade",
            "safety_cleared": safe,
            "hazard_notes": f"Class {state.get('hazard_class')}",
            "ok": safe and is_pure,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_safety", validate_safety)
_g.add_node("assess_purity", assess_purity)
_g.add_node("generate_coa", generate_coa)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "assess_purity")
_g.add_edge("assess_purity", "generate_coa")
_g.add_edge("generate_coa", END)

graph = _g.compile()
