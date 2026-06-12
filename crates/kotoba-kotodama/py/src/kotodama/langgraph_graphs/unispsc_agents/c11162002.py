# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162002 — Phosphate (segment 11).

Bespoke graph logic for handling phosphate mineral data processing,
including purity analysis, moisture validation, and commercial grading.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162002"
UNISPSC_TITLE = "Phosphate"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Phosphate domain state
    p2o5_content: float
    moisture_level: float
    product_grade: str
    safety_audit_passed: bool


def validate_purity(state: State) -> dict[str, Any]:
    """Validates the mineral purity and moisture content for phosphate processing."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 0.0))
    p2o5 = float(inp.get("p2o5", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_purity"],
        "moisture_level": moisture,
        "p2o5_content": p2o5,
        "safety_audit_passed": moisture < 10.0
    }


def grade_phosphate(state: State) -> dict[str, Any]:
    """Assigns a commercial grade based on phosphorus pentoxide (P2O5) concentration."""
    content = state.get("p2o5_content", 0.0)

    if content > 32.0:
        grade = "Premium Agricultural"
    elif content > 28.0:
        grade = "Standard Feed"
    else:
        grade = "Industrial Technical"

    return {
        "log": [f"{UNISPSC_CODE}:grade_phosphate"],
        "product_grade": grade
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Emits the final phosphate specification result manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "grade": state.get("product_grade"),
                "p2o5_percentage": state.get("p2o5_content"),
                "moisture_level": state.get("moisture_level"),
                "audit": "passed" if state.get("safety_audit_passed") else "failed"
            },
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("validate_purity", validate_purity)
_g.add_node("grade_phosphate", grade_phosphate)
_g.add_node("generate_manifest", generate_manifest)

_g.add_edge(START, "validate_purity")
_g.add_edge("validate_purity", "grade_phosphate")
_g.add_edge("grade_phosphate", "generate_manifest")
_g.add_edge("generate_manifest", END)

graph = _g.compile()
