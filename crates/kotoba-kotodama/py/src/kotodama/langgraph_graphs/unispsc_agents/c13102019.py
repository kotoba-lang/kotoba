# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102019 — Commodity.
This bespoke implementation handles state transitions for commodity-grade
polyester resins, focusing on purity validation and viscosity grading.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102019"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102019"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain state for Resin Commodities
    purity_level: float
    viscosity_cps: int
    thermal_stability_ok: bool
    batch_grade: str


def inspect_composition(state: State) -> dict[str, Any]:
    """Inspects the raw chemical composition and verifies initial purity."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.96)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "purity_level": purity,
        "thermal_stability_ok": purity > 0.94,
    }


def analyze_viscosity(state: State) -> dict[str, Any]:
    """Analyzes material viscosity to determine the appropriate industrial grade."""
    inp = state.get("input") or {}
    visc = inp.get("viscosity", 2500)
    purity = state.get("purity_level", 0.0)

    if purity > 0.99 and 2000 <= visc <= 3000:
        grade = "High-Performance"
    elif purity > 0.95:
        grade = "Standard-Commercial"
    else:
        grade = "Utility-Industrial"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_viscosity"],
        "viscosity_cps": visc,
        "batch_grade": grade,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final commodity manifest and certification record."""
    is_compliant = state.get("thermal_stability_ok", False)
    grade = state.get("batch_grade", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "grade": grade,
            "purity": state.get("purity_level"),
            "certified": is_compliant,
            "segment_group": "Resins and Rosins",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_composition", inspect_composition)
_g.add_node("analyze_viscosity", analyze_viscosity)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "analyze_viscosity")
_g.add_edge("analyze_viscosity", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
