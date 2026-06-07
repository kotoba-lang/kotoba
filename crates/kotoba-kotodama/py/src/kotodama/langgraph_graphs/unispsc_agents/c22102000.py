# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22102000 — Fastener (segment 22).

Bespoke graph logic for fastener specification, material validation,
and mechanical property assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22102000"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22102000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Fastener
    material_grade: str
    thread_pitch: str
    corrosion_rating: str
    tensile_strength_mpa: int


def inspect_material(state: State) -> dict[str, Any]:
    """Validates material composition and assigns a corrosion resistance rating."""
    inp = state.get("input") or {}
    mat = inp.get("material", "Carbon Steel")
    grade = inp.get("grade", "8.8")

    # Simple logic to determine environmental suitability
    rating = "C4 (High)" if "Stainless" in mat else "C2 (Medium)"
    if "Zinc" in mat or "Galvanized" in mat:
        rating = "C3 (Urban)"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "material_grade": f"{mat} Grade {grade}",
        "corrosion_rating": rating,
    }


def evaluate_mechanicals(state: State) -> dict[str, Any]:
    """Calculates theoretical tensile strength based on material grade."""
    inp = state.get("input") or {}
    pitch = inp.get("pitch", "Metric Coarse")

    # Simulation of mechanical property lookup
    grade_str = state.get("material_grade") or ""
    if "12.9" in grade_str:
        strength = 1220
    elif "10.9" in grade_str:
        strength = 1040
    elif "8.8" in grade_str:
        strength = 800
    else:
        strength = 400

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_mechanicals"],
        "thread_pitch": pitch,
        "tensile_strength_mpa": strength,
    }


def finalize_catalog_entry(state: State) -> dict[str, Any]:
    """Compiles the technical specification for the fastener catalog."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "technical_specs": {
                "material": state.get("material_grade"),
                "thread": state.get("thread_pitch"),
                "tensile_strength": f"{state.get('tensile_strength_mpa')} MPa",
                "corrosion_resistance": state.get("corrosion_rating"),
            },
            "certified": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_material", inspect_material)
_g.add_node("evaluate_mechanicals", evaluate_mechanicals)
_g.add_node("finalize_catalog_entry", finalize_catalog_entry)

_g.add_edge(START, "inspect_material")
_g.add_edge("inspect_material", "evaluate_mechanicals")
_g.add_edge("evaluate_mechanicals", "finalize_catalog_entry")
_g.add_edge("finalize_catalog_entry", END)

graph = _g.compile()
