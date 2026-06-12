# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12142208 — Metal Powder.
This agent validates the metallurgical properties and particle size distribution
for metal powders used in industrial applications.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12142208"
UNISPSC_TITLE = "Metal Powder"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12142208"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    particle_size_microns: float
    purity_percentage: float
    alloy_grade: str
    is_certified: bool


def inspect_dimensions(state: State) -> dict[str, Any]:
    """Evaluates particle size distribution via mesh analysis simulation."""
    inp = state.get("input") or {}
    size = float(inp.get("particle_size", 50.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_dimensions: size={size}um"],
        "particle_size_microns": size,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes chemical purity and alloy classification."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 99.5))
    grade = str(inp.get("alloy_grade", "Standard-316L"))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition: purity={purity}%, grade={grade}"],
        "purity_percentage": purity,
        "alloy_grade": grade,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Finalizes quality assurance results and generates Certificate of Analysis."""
    size = state.get("particle_size_microns", 0.0)
    purity = state.get("purity_percentage", 0.0)

    # Requirement: fine powder (<150um) and high purity (>99.0%)
    is_compliant = size < 150.0 and purity > 99.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification: compliant={is_compliant}"],
        "is_certified": is_compliant,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "compliant": is_compliant,
            "analysis": {
                "size_microns": size,
                "purity_pct": purity,
                "grade": state.get("alloy_grade")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_dimensions", inspect_dimensions)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "inspect_dimensions")
_g.add_edge("inspect_dimensions", "analyze_composition")
_g.add_edge("analyze_composition", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
