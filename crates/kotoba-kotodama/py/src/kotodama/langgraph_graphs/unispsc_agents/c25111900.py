# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111900 — Marine Spec (segment 25).

Bespoke logic for marine specialty vehicle specifications, hydrodynamic
calculations, and safety certification verification.
"""

from __future__ import annotations

import operator
# Use Annotated from typing for Python 3.9+ compatibility
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111900"
UNISPSC_TITLE = "Marine Spec"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Marine Spec specific domain fields
    vessel_classification: str
    displacement_mt: float
    propulsion_system: str
    hull_verified: bool
    safety_rating: float


def validate_hull_integrity(state: State) -> dict[str, Any]:
    """Inspects input for marine engineering and hull requirements."""
    inp = state.get("input") or {}
    v_class = inp.get("vessel_class", "Specialty Craft")
    # Simulation of hull integrity verification based on provided specs
    hull_ok = "hull_id" in inp and inp.get("material") in ["Steel", "Aluminum", "GRP"]
    return {
        "log": [f"{UNISPSC_CODE}:validate_hull_integrity"],
        "vessel_classification": v_class,
        "hull_verified": hull_ok,
    }


def compute_hydrostatics(state: State) -> dict[str, Any]:
    """Calculates displacement and propulsion requirements."""
    inp = state.get("input") or {}
    # Dimensions for specialty marine craft (defaults provided if missing)
    length = float(inp.get("length_m", 30.0))
    beam = float(inp.get("beam_m", 8.0))
    draft = float(inp.get("draft_m", 3.5))

    # Block coefficient (Cb) for specialty hull forms (approximate)
    cb = float(inp.get("block_coefficient", 0.62))
    # Seawater density approx 1.025 t/m^3
    displacement = length * beam * draft * cb * 1.025

    propulsion = inp.get("propulsion", "Direct Drive Diesel")
    return {
        "log": [f"{UNISPSC_CODE}:compute_hydrostatics"],
        "displacement_mt": round(displacement, 2),
        "propulsion_system": propulsion,
    }


def certify_maritime_spec(state: State) -> dict[str, Any]:
    """Finalizes the marine specification and assigns a safety rating."""
    hull_ok = state.get("hull_verified", False)
    disp = state.get("displacement_mt", 0.0)

    # Simple safety rating heuristic
    rating = 0.0
    if hull_ok:
        rating += 0.5
    if disp > 0:
        rating += 0.4
    if state.get("propulsion_system"):
        rating += 0.1

    return {
        "log": [f"{UNISPSC_CODE}:certify_maritime_spec"],
        "safety_rating": rating,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel_metadata": {
                "classification": state.get("vessel_classification"),
                "displacement": disp,
                "propulsion": state.get("propulsion_system"),
            },
            "certification": {
                "hull_verified": hull_ok,
                "safety_score": rating,
                "status": "APPROVED" if rating >= 0.9 else "PROVISIONAL",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_hull_integrity)
_g.add_node("calculate", compute_hydrostatics)
_g.add_node("certify", certify_maritime_spec)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
