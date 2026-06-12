# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173811 — Shaft (segment 25).

Bespoke graph logic for mechanical shaft specifications and validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173811"
UNISPSC_TITLE = "Shaft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173811"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for "Shaft"
    alloy_grade: str
    machining_tolerance_um: int
    surface_finish_ra: float
    inspection_passed: bool


def configure_material(state: State) -> dict[str, Any]:
    """Node: Configure the metallurgical properties for the shaft."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "AISI 4140")
    return {
        "log": [f"{UNISPSC_CODE}:configure_material alloy={alloy}"],
        "alloy_grade": alloy,
    }


def analyze_tolerances(state: State) -> dict[str, Any]:
    """Node: Analyze the required machining tolerances and surface finish."""
    inp = state.get("input") or {}
    # Precision requirements in micrometers and roughness average
    tolerance = inp.get("tolerance_um", 10)
    surface = inp.get("surface_ra", 0.8)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_tolerances tolerance={tolerance}um surface={surface}Ra"],
        "machining_tolerance_um": tolerance,
        "surface_finish_ra": surface,
    }


def validate_specs(state: State) -> dict[str, Any]:
    """Node: Validate that the shaft specifications meet industrial safety standards."""
    alloy = state.get("alloy_grade", "Unknown")
    tolerance = state.get("machining_tolerance_um", 0)

    # Simple validation logic: shafts must have positive tolerance and known alloy
    passed = bool(alloy != "Unknown" and tolerance > 0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs passed={passed}"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "alloy": alloy,
                "precision": f"{tolerance}um",
                "finish": f"{state.get('surface_finish_ra')}Ra",
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_material)
_g.add_node("analyze", analyze_tolerances)
_g.add_node("validate", validate_specs)

_g.add_edge(START, "configure")
_g.add_edge("configure", "analyze")
_g.add_edge("analyze", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
