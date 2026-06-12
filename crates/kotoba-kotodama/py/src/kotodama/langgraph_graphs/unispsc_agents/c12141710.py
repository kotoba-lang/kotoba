# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141710"
UNISPSC_TITLE = "Resin"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    viscosity_cps: int
    purity_grade: float
    curing_threshold_min: int
    chemical_stability_index: float


def inspect_raw_resin(state: State) -> dict[str, Any]:
    """Inspects raw resin input for basic physical properties."""
    inp = state.get("input") or {}
    visc = inp.get("viscosity", 1200)
    purity = inp.get("purity", 0.99)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_resin"],
        "viscosity_cps": visc,
        "purity_grade": purity,
        "chemical_stability_index": 0.85 if purity > 0.98 else 0.70
    }


def analyze_curing_profile(state: State) -> dict[str, Any]:
    """Determines the curing behavior based on viscosity and stability."""
    visc = state.get("viscosity_cps", 0)
    stability = state.get("chemical_stability_index", 0.0)

    # Heuristic curing time calculation: higher viscosity and stability increase curing duration
    curing_time = int(20 + (visc / 100) * stability)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_curing_profile"],
        "curing_threshold_min": curing_time
    }


def finalize_resin_specification(state: State) -> dict[str, Any]:
    """Produces the final technical datasheet for the resin lot."""
    purity = state.get("purity_grade", 0.0)
    curing = state.get("curing_threshold_min", 0)

    # Quality gate: must meet minimum purity standards
    passed = purity >= 0.95

    return {
        "log": [f"{UNISPSC_CODE}:finalize_resin_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "APPROVED" if passed else "REJECTED",
            "metrics": {
                "purity": purity,
                "curing_min": curing
            },
            "ok": passed
        }
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_raw_resin)
_g.add_node("analyze", analyze_curing_profile)
_g.add_node("finalize", finalize_resin_specification)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
