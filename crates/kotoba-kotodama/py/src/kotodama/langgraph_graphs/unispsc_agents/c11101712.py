# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101712 — Carbon (segment 11).

Bespoke graph logic for handling carbon mineral processing, allotrope
identification, and purity verification. This agent facilitates the
lifecycle of carbon materials from raw specimen to industrial or
gem-grade certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101712"
UNISPSC_TITLE = "Carbon"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101712"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Carbon
    allotrope_form: str  # e.g., Graphite, Diamond, Graphene
    purity_percentage: float
    mass_carats: float
    is_synthetic: bool
    quality_certified: bool


def inspect_specimen(state: State) -> dict[str, Any]:
    """Analyze the raw input material to determine initial carbon properties."""
    inp = state.get("input") or {}
    source = inp.get("source", "terrestrial_ore")
    initial_allotrope = inp.get("detected_form", "amorphous")
    initial_mass = float(inp.get("weight", 1.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specimen -> {source}"],
        "allotrope_form": initial_allotrope,
        "mass_carats": initial_mass,
        "is_synthetic": "lab" in source.lower(),
        "purity_percentage": 0.82,
    }


def refine_material(state: State) -> dict[str, Any]:
    """Simulate the purification process to increase carbon content."""
    current_purity = state.get("purity_percentage", 0.0)
    allotrope = state.get("allotrope_form", "unknown")

    # Diamonds and Graphene require higher precision refinement
    increment = 0.15 if allotrope == "diamond" else 0.10
    refined_purity = min(0.9999, current_purity + increment)

    return {
        "log": [f"{UNISPSC_CODE}:refine_material -> targeting high purity"],
        "purity_percentage": refined_purity,
    }


def certify_output(state: State) -> dict[str, Any]:
    """Perform final quality check and issue a carbon grade certificate."""
    purity = state.get("purity_percentage", 0.0)
    allotrope = state.get("allotrope_form", "unknown")
    is_lab_grown = state.get("is_synthetic", False)

    is_certified = purity > 0.95
    grade = "Industrial" if purity < 0.99 else "High-Purity"
    if allotrope == "diamond" and purity > 0.99:
        grade = "Gem-Grade"

    return {
        "log": [f"{UNISPSC_CODE}:certify_output -> {grade}"],
        "quality_certified": is_certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "allotrope": allotrope,
            "purity": f"{purity:.4%}",
            "grade": grade,
            "synthetic": is_lab_grown,
            "ok": is_certified,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specimen)
_g.add_node("refine", refine_material)
_g.add_node("certify", certify_output)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "refine")
_g.add_edge("refine", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
