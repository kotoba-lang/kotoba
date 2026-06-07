# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24122002 — Plastic Bottle (segment 24).

Bespoke graph logic for plastic bottle manufacturing and specifications processing.
This implementation handles material validation, production simulation, and quality
assurance steps for plastic container products.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24122002"
UNISPSC_TITLE = "Plastic Bottle"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24122002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_type: str
    volume_ml: int
    recycled_content_pct: float
    is_food_grade: bool
    batch_integrity_check: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the plastic bottle."""
    inp = state.get("input") or {}
    material = inp.get("material", "PET")
    volume = inp.get("volume", 500)
    recycled = inp.get("recycled_pct", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_type": material,
        "volume_ml": volume,
        "recycled_content_pct": recycled,
    }


def simulate_production(state: State) -> dict[str, Any]:
    """Simulates the production environment and material suitability."""
    material = state.get("material_type", "PET")
    # PET, HDPE, and PP are commonly food-grade
    is_food_grade = material.upper() in ["PET", "HDPE", "PP"]

    return {
        "log": [f"{UNISPSC_CODE}:simulate_production"],
        "is_food_grade": is_food_grade,
        "batch_integrity_check": True,
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Final inspection and result emission for the plastic bottle agent."""
    is_ok = state.get("batch_integrity_check", False)

    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_type"),
                "volume_ml": state.get("volume_ml"),
                "recycled_content_pct": state.get("recycled_content_pct"),
                "food_grade": state.get("is_food_grade"),
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("simulate_production", simulate_production)
_g.add_node("quality_assurance", quality_assurance)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "simulate_production")
_g.add_edge("simulate_production", "quality_assurance")
_g.add_edge("quality_assurance", END)

graph = _g.compile()
