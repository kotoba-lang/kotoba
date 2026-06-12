# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112505 — Pallet (segment 24).

Bespoke graph logic for pallet specification validation, load rating calculation,
and international compliance verification (e.g. ISPM-15).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112505"
UNISPSC_TITLE = "Pallet"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Pallet
    material: str
    dimensions_mm: tuple[float, float, float]
    dynamic_load_capacity_kg: float
    static_load_capacity_kg: float
    ispm15_certified: bool


def ingest_specifications(state: State) -> dict[str, Any]:
    """Parses input data for pallet material and dimensions."""
    inp = state.get("input") or {}
    mat = inp.get("material", "wood")
    dims = inp.get("dimensions", (1200.0, 1000.0, 144.0))
    return {
        "log": [f"{UNISPSC_CODE}:ingest_specifications: material={mat}"],
        "material": mat,
        "dimensions_mm": dims,
    }


def calculate_load_rating(state: State) -> dict[str, Any]:
    """Calculates load capacity based on material type."""
    mat = state.get("material", "wood")
    # Logic for common pallet types
    if mat.lower() == "plastic":
        dynamic = 1500.0
        static = 5000.0
    elif mat.lower() == "metal":
        dynamic = 2000.0
        static = 8000.0
    else:  # wood
        dynamic = 1000.0
        static = 4000.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_rating: dyn={dynamic}kg"],
        "dynamic_load_capacity_kg": dynamic,
        "static_load_capacity_kg": static,
    }


def verify_phytosanitary_compliance(state: State) -> dict[str, Any]:
    """Ensures wood pallets meet ISPM-15 standards."""
    mat = state.get("material", "wood")
    # Wood pallets usually require heat treatment or fumigation
    is_compliant = True if mat.lower() != "wood" else state.get("input", {}).get("heat_treated", False)

    return {
        "log": [f"{UNISPSC_CODE}:verify_phytosanitary_compliance: certified={is_compliant}"],
        "ispm15_certified": is_compliant,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": mat,
                "dimensions": state.get("dimensions_mm"),
                "dynamic_load": state.get("dynamic_load_capacity_kg"),
                "ispm15": is_compliant
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specifications)
_g.add_node("calculate", calculate_load_rating)
_g.add_node("verify", verify_phytosanitary_compliance)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "calculate")
_g.add_edge("calculate", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
