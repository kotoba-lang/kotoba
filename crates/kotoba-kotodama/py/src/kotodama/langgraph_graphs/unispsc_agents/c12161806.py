# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12161806 — Adhesives (segment 12).

Bespoke graph for adhesive material processing, specializing in viscosity
validation, curing time calculation, and bonding strength estimation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12161806"
UNISPSC_TITLE = "Adhesives"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12161806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Adhesives
    viscosity_cp: int
    is_hazardous: bool
    bonding_strength_psi: float
    cure_time_min: int


def analyze_material_profile(state: State) -> dict[str, Any]:
    """Inspects the adhesive material profile for viscosity and safety."""
    inp = state.get("input") or {}
    viscosity = inp.get("viscosity", 2500)
    is_haz = inp.get("solvent_base", False)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_material_profile: {viscosity}cP"],
        "viscosity_cp": viscosity,
        "is_hazardous": is_haz,
    }


def compute_bond_specifications(state: State) -> dict[str, Any]:
    """Estimates bonding strength and cure duration based on material properties."""
    v = state.get("viscosity_cp", 2500)
    # Heuristic: Higher viscosity often correlates with higher bond strength in this model
    psi = 1200.0 + (v / 8.0)
    # Heuristic: Thicker adhesives take longer to cure
    cure = 45 if v < 4000 else 180

    return {
        "log": [f"{UNISPSC_CODE}:compute_bond_specifications: {psi}psi, {cure}min"],
        "bonding_strength_psi": psi,
        "cure_time_min": cure,
    }


def certify_technical_batch(state: State) -> dict[str, Any]:
    """Prepares the final technical data sheet and certification status."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_technical_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "data_sheet": {
                "viscosity": state.get("viscosity_cp"),
                "bond_strength": state.get("bonding_strength_psi"),
                "cure_time": state.get("cure_time_min"),
                "is_hazardous": state.get("is_hazardous"),
            },
            "status": "certified",
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_material_profile", analyze_material_profile)
_g.add_node("compute_bond_specifications", compute_bond_specifications)
_g.add_node("certify_technical_batch", certify_technical_batch)

_g.add_edge(START, "analyze_material_profile")
_g.add_edge("analyze_material_profile", "compute_bond_specifications")
_g.add_edge("compute_bond_specifications", "certify_technical_batch")
_g.add_edge("certify_technical_batch", END)

graph = _g.compile()
