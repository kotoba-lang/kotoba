# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11131600 — Catalyst (segment 11).

Bespoke graph logic for catalysts, focusing on active site density verification,
thermal stability assessment, and regeneration cycle validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11131600"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11131600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Catalyst processing
    active_site_density: float
    thermal_stability_passed: bool
    regeneration_potential: str
    efficiency_rating: float


def analyze_active_sites(state: State) -> dict[str, Any]:
    """Evaluates the density of active catalytic sites per unit area."""
    inp = state.get("input") or {}
    density = float(inp.get("site_density", 0.0))
    # Minimum requirement for industrial grade catalysts
    is_sufficient = density > 12.5

    return {
        "log": [f"{UNISPSC_CODE}:analyze_active_sites: density={density} sufficient={is_sufficient}"],
        "active_site_density": density,
    }


def assess_thermal_stability(state: State) -> dict[str, Any]:
    """Checks if the catalyst maintains structural integrity at operating temperatures."""
    inp = state.get("input") or {}
    max_temp = float(inp.get("operating_temp", 450.0))
    threshold = float(inp.get("stability_threshold", 500.0))

    passed = max_temp <= threshold

    # Determine regeneration potential based on stability
    regen = "HIGH" if passed and max_temp < 300.0 else "MODERATE"
    if not passed:
        regen = "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:assess_thermal_stability: passed={passed} regen={regen}"],
        "thermal_stability_passed": passed,
        "regeneration_potential": regen,
    }


def calculate_efficiency(state: State) -> dict[str, Any]:
    """Computes the final catalytic efficiency rating and certification status."""
    stability = state.get("thermal_stability_passed", False)
    density = state.get("active_site_density", 0.0)
    regen = state.get("regeneration_potential", "NONE")

    # Efficiency is a function of density and stability
    efficiency = (density / 100.0) * (0.95 if stability else 0.2)
    ok = stability and density > 10.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_efficiency: efficiency={efficiency:.4f} ok={ok}"],
        "efficiency_rating": efficiency,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if ok else "REJECTED",
            "metrics": {
                "efficiency": round(efficiency, 4),
                "regeneration": regen,
                "stability_check": stability
            }
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_sites", analyze_active_sites)
_g.add_node("assess_stability", assess_thermal_stability)
_g.add_node("calculate", calculate_efficiency)

_g.add_edge(START, "analyze_sites")
_g.add_edge("analyze_sites", "assess_stability")
_g.add_edge("assess_stability", "calculate")
_g.add_edge("calculate", END)

graph = _g.compile()
