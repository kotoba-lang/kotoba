# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101614 — Fastener (segment 22).

Bespoke graph logic for managing industrial fastener specifications, including
material analysis, mechanical properties verification, and batch certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101614"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101614"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Fastener-specific domain fields
    material_grade: str
    thread_spec: str
    tensile_strength: int
    finish_type: str
    certified: bool


def analyze_specifications(state: State) -> dict[str, Any]:
    """Examine input requirements for fastener dimensions and metallurgy."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Grade 2 Low Carbon")
    # Simulate tensile strength mapping based on grade
    strength_map = {
        "Grade 2": 74000,
        "Grade 5": 120000,
        "Grade 8": 150000,
        "Stainless 316": 70000,
    }
    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "material_grade": grade,
        "thread_spec": inp.get("thread", "UNC-2A"),
        "tensile_strength": strength_map.get(grade[:7], 60000),
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Validate mechanical properties against ASTM/ISO standards."""
    material = state.get("material_grade", "")
    is_corrosion_resistant = "Stainless" in material or "Zinc" in material
    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "finish_type": "Passivated" if is_corrosion_resistant else "Plain",
        "certified": state.get("tensile_strength", 0) >= 60000,
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Emit the final Fastener state and certification status."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "grade": state.get("material_grade"),
                "thread": state.get("thread_spec"),
                "psi_rating": state.get("tensile_strength"),
                "finish": state.get("finish_type"),
            },
            "certified": state.get("certified", False),
            "status": "READY_FOR_DISTRIBUTION",
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_specifications)
_g.add_node("verify", verify_compliance)
_g.add_node("finalize", finalize_batch)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
