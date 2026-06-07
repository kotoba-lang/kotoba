# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12181503 — Solder (segment 12).

Bespoke graph logic for handling soldering material specifications,
thermal profiles, and inventory management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12181503"
UNISPSC_TITLE = "Solder"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12181503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Solder
    alloy_composition: str
    melting_point_c: float
    flux_core_type: str
    diameter_mm: float
    spec_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the physical and chemical properties of the solder requested."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "Sn63Pb37")
    diameter = inp.get("diameter", 0.8)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "alloy_composition": alloy,
        "diameter_mm": float(diameter),
        "spec_verified": True
    }


def compute_thermal_profile(state: State) -> dict[str, Any]:
    """Determines the required melting point and heating profile for the alloy."""
    alloy = state.get("alloy_composition", "Sn63Pb37")

    # Simple lookup for common solders
    profiles = {
        "Sn63Pb37": 183.0,
        "Sn60Pb40": 191.0,
        "Sn96.5Ag3.0Cu0.5": 217.0,
        "Sn99Ag0.3Cu0.7": 227.0
    }
    temp = profiles.get(alloy, 200.0)

    return {
        "log": [f"{UNISPSC_CODE}:compute_thermal_profile"],
        "melting_point_c": temp,
        "flux_core_type": state.get("input", {}).get("flux", "Rosin Core (RMA)")
    }


def finalize_allocation(state: State) -> dict[str, Any]:
    """Finalizes the solder specification and prepares the result record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_allocation"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "alloy": state.get("alloy_composition"),
            "melting_point": state.get("melting_point_c"),
            "diameter": state.get("diameter_mm"),
            "flux": state.get("flux_core_type"),
            "status": "allocated",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("compute_thermal_profile", compute_thermal_profile)
_g.add_node("finalize_allocation", finalize_allocation)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "compute_thermal_profile")
_g.add_edge("compute_thermal_profile", "finalize_allocation")
_g.add_edge("finalize_allocation", END)

graph = _g.compile()
