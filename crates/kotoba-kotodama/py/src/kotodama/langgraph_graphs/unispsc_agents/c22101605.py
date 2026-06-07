# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101605 — Fastener (segment 22).
Bespoke logic for managing fastener specifications and structural integrity checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101605"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fasteners
    fastener_type: str
    material_grade: str
    tensile_strength_mpa: float
    is_corrosion_resistant: bool
    thread_pitch: str


def inspect_spec(state: State) -> dict[str, Any]:
    """Inspects the input for fastener specifications and type categorization."""
    inp = state.get("input") or {}
    f_type = inp.get("type", "standard_bolt")
    grade = inp.get("grade", "8.8")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "fastener_type": f_type,
        "material_grade": grade,
        "thread_pitch": inp.get("pitch", "metric_fine")
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Verifies material integrity and safety metrics based on grade and type."""
    grade = state.get("material_grade", "8.8")
    f_type = state.get("fastener_type", "standard_bolt")

    # Simulated strength calculation based on grade
    try:
        strength = float(grade.split('.')[0]) * 100.0
    except (ValueError, AttributeError):
        strength = 400.0

    corrosion = "stainless" in f_type.lower() or "galvanized" in f_type.lower()

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "tensile_strength_mpa": strength,
        "is_corrosion_resistant": corrosion,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Finalizes the fastener data and assigns a certification status."""
    strength = state.get("tensile_strength_mpa", 0.0)
    is_res = state.get("is_corrosion_resistant", False)

    status = "high_tensile_certified" if strength >= 800 else "standard_grade"
    if is_res:
        status += "_marine_ready"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "type": state.get("fastener_type"),
                "grade": state.get("material_grade"),
                "tensile_strength": strength,
                "thread_pitch": state.get("thread_pitch"),
            },
            "certification_status": status,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("verify_integrity", verify_integrity)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "verify_integrity")
_g.add_edge("verify_integrity", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
