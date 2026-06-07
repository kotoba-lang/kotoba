# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121502 — Packaging (segment 24).

Bespoke graph logic for packaging specifications, material validation,
and capacity calculation. This agent manages the lifecycle of packaging
design and verification within the material handling segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121502"
UNISPSC_TITLE = "Packaging"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Packaging
    material_type: str
    dimensions_verified: bool
    weight_capacity_kg: float
    sustainability_rating: str
    is_fragile: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Inspects the input for packaging material and dimensions."""
    inp = state.get("input") or {}
    material = inp.get("material", "corrugated_cardboard")
    width = inp.get("width", 0)
    height = inp.get("height", 0)
    depth = inp.get("depth", 0)

    verified = all(v > 0 for v in [width, height, depth])

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "material_type": material,
        "dimensions_verified": verified,
        "is_fragile": inp.get("fragile", False)
    }


def calculate_capacity(state: State) -> dict[str, Any]:
    """Calculates weight capacity and assigns sustainability rating."""
    material = state.get("material_type", "unknown")

    # Simple logic to simulate capacity calculation
    capacities = {
        "corrugated_cardboard": 25.0,
        "plastic_hdpe": 50.0,
        "wood_pallet": 1000.0,
        "bioplastic": 15.0
    }

    ratings = {
        "corrugated_cardboard": "A",
        "plastic_hdpe": "C",
        "wood_pallet": "B",
        "bioplastic": "A+"
    }

    return {
        "log": [f"{UNISPSC_CODE}:calculate_capacity"],
        "weight_capacity_kg": capacities.get(material, 10.0),
        "sustainability_rating": ratings.get(material, "N/A")
    }


def finalize_packaging_plan(state: State) -> dict[str, Any]:
    """Finalizes the packaging result based on inspections."""
    is_valid = state.get("dimensions_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_packaging_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "ready" if is_valid else "spec_error",
            "material": state.get("material_type"),
            "max_load": state.get("weight_capacity_kg"),
            "eco_score": state.get("sustainability_rating"),
            "ok": is_valid
        }
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specifications)
_g.add_node("calculate", calculate_capacity)
_g.add_node("finalize", finalize_packaging_plan)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
