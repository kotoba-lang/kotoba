# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141100 — Drilling Part (segment 20).

This module provides bespoke LangGraph logic for managing drilling part
specifications, material durability assessments, and compliance verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141100"
UNISPSC_TITLE = "Drilling Part"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Drilling Parts
    part_identifier: str
    material_grade: str
    tensile_strength_mpa: float
    thread_integrity_verified: bool
    inspection_outcome: str


def analyze_specifications(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the drilling part."""
    inp = state.get("input") or {}
    p_id = inp.get("part_id", "DR-DEFAULT-001")
    m_grade = inp.get("material", "HardenedSteel-T1")

    # Logic: Verify if the thread type is provided in input
    has_thread = "thread_spec" in inp

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "part_identifier": p_id,
        "material_grade": m_grade,
        "thread_integrity_verified": has_thread,
    }


def assess_durability(state: State) -> dict[str, Any]:
    """Calculates theoretical tensile strength and assigns an inspection status."""
    grade = state.get("material_grade", "Standard")

    # Simulated material science calculation
    strength = 850.0 if "Hardened" in grade else 400.0

    status = "Approved" if strength >= 500.0 and state.get("thread_integrity_verified") else "Requires Review"

    return {
        "log": [f"{UNISPSC_CODE}:assess_durability"],
        "tensile_strength_mpa": strength,
        "inspection_outcome": status,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Wraps the state into a finalized result for the Drilling Part actor."""
    outcome = state.get("inspection_outcome", "Unknown")
    is_ok = outcome == "Approved"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "part_id": state.get("part_identifier"),
                "grade": state.get("material_grade"),
                "strength": state.get("tensile_strength_mpa"),
            },
            "certified": is_ok,
            "status": outcome,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_specifications", analyze_specifications)
_g.add_node("assess_durability", assess_durability)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "analyze_specifications")
_g.add_edge("analyze_specifications", "assess_durability")
_g.add_edge("assess_durability", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
