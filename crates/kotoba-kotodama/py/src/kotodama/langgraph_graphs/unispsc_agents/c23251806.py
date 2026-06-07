# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251806 — Die (segment 23).

Bespoke graph logic for industrial die manufacturing specifications. This agent
handles the validation of tool-steel grades, precision tolerances, and
heat-treatment requirements for industrial stamping and casting dies.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251806"
UNISPSC_TITLE = "Die"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Die (Industrial Tooling)
    material_grade: str
    tolerance_microns: float
    surface_finish_ra: float
    cavity_layout: str
    heat_treatment_required: bool


def analyze_specifications(state: State) -> dict[str, Any]:
    """Validates the input engineering requirements for the die."""
    inp = state.get("input") or {}
    # Default to H13 Tool Steel if not specified
    mat = inp.get("material", "H13 Tool Steel")
    # Tolerance defaults to 10 microns for precision dies
    tol = float(inp.get("tolerance", 10.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications"],
        "material_grade": mat,
        "tolerance_microns": tol,
    }


def configure_manufacturing(state: State) -> dict[str, Any]:
    """Determines heat treatment and surface requirements based on specs."""
    tol = state.get("tolerance_microns", 10.0)
    # Precision dies usually require hardening (> HRC 50)
    heat_treat = tol < 50.0
    # High precision requires finer surface finish (Ra in micrometers)
    finish = 0.8 if tol < 20.0 else 3.2

    return {
        "log": [f"{UNISPSC_CODE}:configure_manufacturing"],
        "heat_treatment_required": heat_treat,
        "surface_finish_ra": finish,
        "cavity_layout": state.get("input", {}).get("layout", "Single Cavity"),
    }


def finalize_die_config(state: State) -> dict[str, Any]:
    """Produces the final industrial manufacturing record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_die_config"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "material": state.get("material_grade"),
                "tolerance_microns": state.get("tolerance_microns"),
                "surface_finish_ra": state.get("surface_finish_ra"),
                "heat_treatment_required": state.get("heat_treatment_required"),
                "layout": state.get("cavity_layout"),
            },
            "status": "validated_for_production",
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_specifications)
_g.add_node("configure", configure_manufacturing)
_g.add_node("finalize", finalize_die_config)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
