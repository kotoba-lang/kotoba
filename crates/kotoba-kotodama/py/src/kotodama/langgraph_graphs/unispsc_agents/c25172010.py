# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172010 — Sway Bar (segment 25).
Bespoke logic for vehicle suspension stabilization components.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172010"
UNISPSC_TITLE = "Sway Bar"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172010"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Sway Bar
    torsion_rate_nm: float
    bushing_compatibility: bool
    vehicle_model_match: str
    safety_rating: str


def inspect_spec(state: State) -> dict[str, Any]:
    """Node: Validates sway bar specifications against vehicle requirements."""
    inp = state.get("input") or {}
    model = inp.get("vehicle_model", "generic_platform")
    diameter = inp.get("bar_diameter_mm", 0.0)

    # Simple logic to simulate inspection
    compatible = diameter > 15.0  # Minimal diameter for safety stabilization

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "vehicle_model_match": model,
        "bushing_compatibility": compatible,
    }


def calculate_dynamics(state: State) -> dict[str, Any]:
    """Node: Calculates torsional stiffness and roll resistance."""
    inp = state.get("input") or {}
    diameter = inp.get("bar_diameter_mm", 22.0)

    # Torsional stiffness is proportional to d^4; simplified model
    rate = (diameter ** 4) * 0.01

    rating = "standard"
    if rate > 2500:
        rating = "performance"
    elif rate < 500:
        rating = "utility"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_dynamics"],
        "torsion_rate_nm": round(rate, 2),
        "safety_rating": rating,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Node: Prepares the final UNISPSC asset record and fitment report."""
    is_verified = state.get("bushing_compatibility", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "torsion_rate": state.get("torsion_rate_nm"),
                "rating": state.get("safety_rating"),
                "fitment": state.get("vehicle_model_match"),
            },
            "status": "active_catalog" if is_verified else "pending_review",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("calculate_dynamics", calculate_dynamics)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "calculate_dynamics")
_g.add_edge("calculate_dynamics", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
