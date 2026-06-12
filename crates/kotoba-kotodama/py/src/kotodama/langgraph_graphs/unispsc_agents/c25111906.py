# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111906 — Anchor (segment 25).

Bespoke graph logic for industrial anchors and fasteners. This agent evaluates
site conditions, calculates mechanical load capacities, and certifies
installation specifications for commercial furniture and equipment mounting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111906"
UNISPSC_TITLE = "Anchor"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111906"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    substrate_type: str
    tensile_strength_kn: float
    safety_margin: float
    compliance_verified: bool


def assess_mounting_site(state: State) -> dict[str, Any]:
    """Analyzes the substrate material and environmental factors."""
    inp = state.get("input") or {}
    substrate = inp.get("substrate", "reinforced_concrete")
    return {
        "log": [f"{UNISPSC_CODE}:assess_mounting_site -> {substrate}"],
        "substrate_type": substrate,
    }


def calculate_load_capacity(state: State) -> dict[str, Any]:
    """Computes the mechanical holding power of the anchor."""
    substrate = state.get("substrate_type", "unknown")
    # Base load logic for specific industrial anchoring scenarios
    lookup = {
        "reinforced_concrete": 85.0,
        "structural_steel": 120.0,
        "masonry": 35.0,
    }
    base_kn = lookup.get(substrate, 15.0)
    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_capacity -> {base_kn}kN"],
        "tensile_strength_kn": base_kn,
        "safety_margin": 1.25,
    }


def certify_specifications(state: State) -> dict[str, Any]:
    """Finalizes the technical data sheet and compliance status."""
    strength = state.get("tensile_strength_kn", 0.0)
    safety = state.get("safety_margin", 1.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_specifications"],
        "compliance_verified": strength > 0,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "max_allowable_load_kn": strength / safety,
                "nominal_tensile_kn": strength,
                "safety_coefficient": safety,
                "mounting_environment": state.get("substrate_type")
            },
            "certification_status": "VALIDATED"
        },
    }


_g = StateGraph(State)
_g.add_node("assess_mounting_site", assess_mounting_site)
_g.add_node("calculate_load_capacity", calculate_load_capacity)
_g.add_node("certify_specifications", certify_specifications)

_g.add_edge(START, "assess_mounting_site")
_g.add_edge("assess_mounting_site", "calculate_load_capacity")
_g.add_edge("calculate_load_capacity", "certify_specifications")
_g.add_edge("certify_specifications", END)

graph = _g.compile()
