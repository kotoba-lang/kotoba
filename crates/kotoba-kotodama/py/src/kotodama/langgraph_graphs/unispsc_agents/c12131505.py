# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12131505 — Chemical (segment 12).

Custom graph implementation for Chemical lifecycle management, including
substance identification, hazard assessment, and specification registration.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131505"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    chemical_formula: str
    hazard_index: int
    storage_temp_c: float
    is_flammable: bool


def identify_substance(state: State) -> dict[str, Any]:
    """Identifies the chemical substance and its molecular formula from input."""
    inp = state.get("input") or {}
    formula = str(inp.get("formula", "Unknown"))
    flammable = bool(inp.get("flammable", False))
    return {
        "log": [f"{UNISPSC_CODE}:identify_substance"],
        "chemical_formula": formula,
        "is_flammable": flammable,
    }


def assess_hazard_profile(state: State) -> dict[str, Any]:
    """Evaluates safety risks and determines storage temperature requirements."""
    inp = state.get("input") or {}
    reactivity = int(inp.get("reactivity_level", 0))
    is_volatile = bool(inp.get("is_volatile", False))
    is_flammable = state.get("is_flammable", False)

    # Calculate basic hazard index based on reactivity and volatility
    index = reactivity + (1 if is_volatile else 0) + (2 if is_flammable else 0)

    # Cooler storage for more hazardous materials
    target_temp = 20.0
    if index >= 3:
        target_temp = 4.0
    elif index >= 1:
        target_temp = 15.0

    return {
        "log": [f"{UNISPSC_CODE}:assess_hazard_profile"],
        "hazard_index": index,
        "storage_temp_c": target_temp,
    }


def register_specification(state: State) -> dict[str, Any]:
    """Finalizes the chemical profile with regulatory and storage metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:register_specification"],
        "result": {
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "segment": UNISPSC_SEGMENT,
                "did": UNISPSC_DID,
            },
            "properties": {
                "formula": state.get("chemical_formula"),
                "hazard_rating": state.get("hazard_index"),
                "flammable": state.get("is_flammable"),
            },
            "logistical_requirements": {
                "storage_temp": f"{state.get('storage_temp_c')}C",
            },
            "status": "ready",
        },
    }


_g = StateGraph(State)

_g.add_node("identify", identify_substance)
_g.add_node("hazard_assessment", assess_hazard_profile)
_g.add_node("register", register_specification)

_g.add_edge(START, "identify")
_g.add_edge("identify", "hazard_assessment")
_g.add_edge("hazard_assessment", "register")
_g.add_edge("register", END)

graph = _g.compile()
