# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251804 — Die (segment 23).

This bespoke LangGraph logic handles the specifications and tolerance
validation for industrial dies used in manufacturing processes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251804"
UNISPSC_TITLE = "Die"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Die manufacturing
    material_type: str
    precision_grade: str
    tolerance_microns: float
    surface_finish_ra: float
    die_id: str


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the input specifications for the die tool."""
    inp = state.get("input") or {}
    mat = inp.get("material", "Hardened Tool Steel")
    prec = inp.get("precision", "Standard")

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec -> material: {mat}"],
        "material_type": mat,
        "precision_grade": prec,
    }


def calculate_tolerances(state: State) -> dict[str, Any]:
    """Calculates allowable tolerances based on material and precision grade."""
    prec = state.get("precision_grade", "Standard")

    # Simple logic to determine tolerance requirements
    if prec == "High":
        tol = 2.5
        finish = 0.4
    else:
        tol = 10.0
        finish = 1.6

    return {
        "log": [f"{UNISPSC_CODE}:calculate_tolerances -> tol: {tol}μm"],
        "tolerance_microns": tol,
        "surface_finish_ra": finish,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the die asset configuration and generates the DID record."""
    die_id = f"DIE-{UNISPSC_CODE}-{hash(state.get('material_type')) % 10000}"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset -> ID: {die_id}"],
        "die_id": die_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "asset_id": die_id,
            "specs": {
                "material": state.get("material_type"),
                "tolerance": state.get("tolerance_microns"),
                "surface_finish": state.get("surface_finish_ra"),
            },
            "status": "ready_for_production",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_spec", validate_spec)
_g.add_node("calculate_tolerances", calculate_tolerances)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "validate_spec")
_g.add_edge("validate_spec", "calculate_tolerances")
_g.add_edge("calculate_tolerances", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
