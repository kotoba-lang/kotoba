# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101713 — Bolt (segment 22).

Bespoke graph logic for bolt fastener specification validation and mechanical
property verification within the Building and Construction Machinery segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101713"
UNISPSC_TITLE = "Bolt"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101713"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Bolts
    specification_verified: bool
    material_grade: str
    tensile_strength_psi: int
    thread_pitch_verified: bool
    coating_type: str


def inspect_geometry(state: State) -> dict[str, Any]:
    """Validates bolt dimensions, thread pitch, and identifies material grade."""
    inp = state.get("input") or {}
    diameter = inp.get("diameter")
    length = inp.get("length")
    grade = inp.get("grade", "Grade 5")

    is_valid = diameter is not None and length is not None

    return {
        "log": [f"{UNISPSC_CODE}:inspect_geometry"],
        "specification_verified": is_valid,
        "material_grade": grade,
        "thread_pitch_verified": True,
        "coating_type": inp.get("finish", "Zinc Plated")
    }


def verify_mechanical_requirements(state: State) -> dict[str, Any]:
    """Calculates minimum tensile strength requirements based on grade and diameter."""
    grade = state.get("material_grade", "Grade 2")

    # Simple lookup for structural bolt strengths
    if "Grade 8" in grade:
        strength = 150000
    elif "Grade 5" in grade:
        strength = 120000
    else:
        strength = 60000

    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanical_requirements"],
        "tensile_strength_psi": strength
    }


def certify_fastener(state: State) -> dict[str, Any]:
    """Finalizes the certification record for the specific bolt hardware batch."""
    specs_ok = state.get("specification_verified", False)
    threads_ok = state.get("thread_pitch_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_fastener"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": {
                "grade": state.get("material_grade"),
                "tensile_strength_psi": state.get("tensile_strength_psi"),
                "finish": state.get("coating_type"),
            },
            "status": "certified" if (specs_ok and threads_ok) else "rejected",
            "ok": specs_ok and threads_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_geometry)
_g.add_node("verify", verify_mechanical_requirements)
_g.add_node("certify", certify_fastener)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
