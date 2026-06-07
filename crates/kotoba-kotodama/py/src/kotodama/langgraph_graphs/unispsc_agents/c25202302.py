# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202302 — Harness.

This agent handles the lifecycle of vehicle harness components, specifically
focusing on safety harness structural integrity, material validation, and
compliance certification within the automotive and commercial vehicle segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202302"
UNISPSC_TITLE = "Harness"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202302"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Harness
    material_type: str
    tensile_strength_kn: float
    integrity_verified: bool
    safety_rating: str


def validate_spec(state: State) -> dict[str, Any]:
    """Initial validation of harness material and design specifications."""
    inp = state.get("input") or {}
    m_type = inp.get("material", "Polyester-HighTenacity")
    strength = float(inp.get("target_strength", 22.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec -> {m_type} at {strength}kN"],
        "material_type": m_type,
        "tensile_strength_kn": strength,
        "integrity_verified": False,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Simulates structural stress testing and buckle mechanism verification."""
    strength = state.get("tensile_strength_kn", 0.0)
    # Simulation: Harnesses must exceed 20kN for commercial vehicle safety
    passed = strength >= 20.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity -> Pass={passed}"],
        "integrity_verified": passed,
    }


def certify_harness(state: State) -> dict[str, Any]:
    """Finalizes the safety rating and emits the certification result."""
    verified = state.get("integrity_verified", False)
    rating = "AS-6102-SECURE" if verified else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:certify_harness -> Rating={rating}"],
        "safety_rating": rating,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if verified else "FAILED_INSPECTION",
            "rating": rating,
            "material": state.get("material_type"),
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_spec)
_g.add_node("verify_integrity", verify_integrity)
_g.add_node("certify_harness", certify_harness)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "verify_integrity")
_g.add_edge("verify_integrity", "certify_harness")
_g.add_edge("certify_harness", END)

graph = _g.compile()
