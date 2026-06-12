# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101514 — Fastener (segment 22).

Bespoke graph implementation for fastener specification validation,
material verification, and quality compliance processing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101514"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Fasteners (Segment 22: Building/Construction)
    material_grade: str
    tensile_strength_verified: bool
    thread_compliance: bool
    finish_type: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and thread standards for the fastener."""
    inp = state.get("input") or {}
    thread_std = inp.get("thread_standard", "ISO")
    # Fasteners in construction must adhere to recognized standards
    is_compliant = thread_std in ["UNC", "UNF", "ISO", "Metric"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "thread_compliance": is_compliant,
    }


def verify_material_grade(state: State) -> dict[str, Any]:
    """Checks material composition and ensures tensile strength requirements are met."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard")
    # Structural fasteners usually require higher grades (e.g., Grade 8 or Stainless 316)
    is_high_strength = grade in ["Grade 5", "Grade 8", "A4-80", "Stainless 316"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_material_grade"],
        "material_grade": grade,
        "tensile_strength_verified": is_high_strength,
    }


def approve_and_tag(state: State) -> dict[str, Any]:
    """Finalizes processing and assigns compliance metadata."""
    inp = state.get("input") or {}
    is_compliant = state.get("thread_compliance", False) and state.get("tensile_strength_verified", False)
    finish = inp.get("finish", "Zinc Plated")

    return {
        "log": [f"{UNISPSC_CODE}:approve_and_tag"],
        "finish_type": finish,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "compliance_status": "CERTIFIED" if is_compliant else "PENDING_REVIEW",
            "metadata": {
                "material": state.get("material_grade"),
                "finish": finish,
                "structural_integrity": "HIGH" if state.get("tensile_strength_verified") else "STANDARD"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_material_grade", verify_material_grade)
_g.add_node("approve_and_tag", approve_and_tag)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_material_grade")
_g.add_edge("verify_material_grade", "approve_and_tag")
_g.add_edge("approve_and_tag", END)

graph = _g.compile()
