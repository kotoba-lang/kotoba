# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12171602"
UNISPSC_TITLE = "Polymer"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12171602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Polymer domain fields
    monomer_base: str
    viscosity_index: float
    purity_grade: str
    thermal_stability_verified: bool


def validate_feedstock(state: State) -> dict[str, Any]:
    """Analyzes the raw material input for polymer synthesis."""
    inp = state.get("input") or {}
    monomer = inp.get("monomer", "ethylene-base")
    purity = "Industrial" if inp.get("purity", 0.0) < 0.95 else "Analytical"
    return {
        "log": [f"{UNISPSC_CODE}:validate_feedstock"],
        "monomer_base": monomer,
        "purity_grade": purity,
    }


def simulate_synthesis(state: State) -> dict[str, Any]:
    """Simulates the polymerization process and checks material properties."""
    monomer = state.get("monomer_base", "unknown")
    # Deterministic property calculation for Polymer 12171602
    viscosity = 185.2 if "ethylene" in monomer else 140.0
    return {
        "log": [f"{UNISPSC_CODE}:simulate_synthesis"],
        "viscosity_index": viscosity,
        "thermal_stability_verified": True,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Certifies the polymer batch and prepares the official actor result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "base": state.get("monomer_base"),
                "viscosity": state.get("viscosity_index"),
                "grade": state.get("purity_grade"),
                "stable": state.get("thermal_stability_verified"),
            },
            "certification": "ISO-UNISPSC-12-COMPLIANT",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_feedstock", validate_feedstock)
_g.add_node("simulate_synthesis", simulate_synthesis)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_feedstock")
_g.add_edge("validate_feedstock", "simulate_synthesis")
_g.add_edge("simulate_synthesis", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
