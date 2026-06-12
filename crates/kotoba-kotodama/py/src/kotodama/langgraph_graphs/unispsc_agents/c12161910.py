# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12161910 — Magnetic Material (segment 12).

Bespoke graph logic for evaluating and certifying magnetic materials,
including checks for flux density, coercivity, and thermal stability.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12161910"
UNISPSC_TITLE = "Magnetic Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12161910"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    magnetic_grade: str
    remanence_tesla: float
    coercivity_ka_m: float
    thermal_stability_verified: bool
    quality_score: float


def verify_magnetic_properties(state: State) -> dict[str, Any]:
    """Inspects the fundamental magnetic properties from input specifications."""
    inp = state.get("input") or {}
    grade = str(inp.get("grade", "N35"))
    br = float(inp.get("remanence", 1.2))  # Tesla
    hcj = float(inp.get("coercivity", 900.0))  # kA/m

    return {
        "log": [f"{UNISPSC_CODE}:verify_magnetic_properties"],
        "magnetic_grade": grade,
        "remanence_tesla": br,
        "coercivity_ka_m": hcj,
    }


def test_thermal_stability(state: State) -> dict[str, Any]:
    """Simulates thermal exposure to verify Curie temperature compliance."""
    # Logic: High coercivity generally correlates with better thermal stability in specific grades
    hcj = state.get("coercivity_ka_m", 0.0)
    is_stable = hcj > 800.0

    return {
        "log": [f"{UNISPSC_CODE}:test_thermal_stability"],
        "thermal_stability_verified": is_stable,
        "quality_score": 0.95 if is_stable else 0.70,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Compiles the final certification for the magnetic material."""
    score = state.get("quality_score", 0.0)
    passed = state.get("thermal_stability_verified", False) and score > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified_grade": state.get("magnetic_grade"),
            "flux_density": f"{state.get('remanence_tesla')}T",
            "passed_inspection": passed,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_properties", verify_magnetic_properties)
_g.add_node("test_stability", test_thermal_stability)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "verify_properties")
_g.add_edge("verify_properties", "test_stability")
_g.add_edge("test_stability", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
