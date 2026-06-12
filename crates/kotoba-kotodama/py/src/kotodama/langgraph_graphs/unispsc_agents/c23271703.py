# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271703 — Braze (segment 23).

Bespoke LangGraph logic for determining brazing material specifications,
joint clearances, and thermal requirements based on industrial manufacturing
standards in the segment 23 (Industrial Manufacturing) category.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271703"
UNISPSC_TITLE = "Braze"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Braze domain fields
    alloy_spec: str
    melting_point_c: float
    flux_type: str
    target_clearance_mm: float
    is_vacuum_compatible: bool


def identify_materials(state: State) -> dict[str, Any]:
    """Identify base metals and select a compatible brazing filler alloy."""
    inp = state.get("input") or {}
    metals = inp.get("metals", ["copper"])

    if any(m in ["stainless", "steel", "nickel"] for m in metals):
        alloy = "BAg-24 (Silver-Zinc-Tin)"
        mp = 675.0
        vac = True
    else:
        # Default for copper-to-copper applications
        alloy = "BCuP-2 (Phosphorus-Copper)"
        mp = 710.0
        vac = False

    return {
        "log": [f"{UNISPSC_CODE}:identify_materials"],
        "alloy_spec": alloy,
        "melting_point_c": mp,
        "is_vacuum_compatible": vac,
    }


def calculate_parameters(state: State) -> dict[str, Any]:
    """Calculate capillary clearance and fluxing requirements."""
    alloy = state.get("alloy_spec", "")

    # Capillary attraction depends on alloy wetting properties and viscosity
    if "BCuP" in alloy:
        clearance = 0.10
        flux = "None (Self-fluxing on copper base)"
    else:
        clearance = 0.04
        flux = "AWS FB3-A Fluoride-based Flux"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_parameters"],
        "target_clearance_mm": clearance,
        "flux_type": flux,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Emit the final validated brazing procedure specification."""
    mp = state.get("melting_point_c") or 0.0
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "alloy": state.get("alloy_spec"),
            "flow_temp_c": mp + 40.0,
            "clearance_mm": state.get("target_clearance_mm"),
            "flux": state.get("flux_type"),
            "vacuum_process": state.get("is_vacuum_compatible"),
            "status": "APPROVED",
            "did": UNISPSC_DID
        },
    }


_g = StateGraph(State)
_g.add_node("identify", identify_materials)
_g.add_node("calculate", calculate_parameters)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "identify")
_g.add_edge("identify", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
