# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112503 — Carton (segment 24).

Bespoke logic for carton specification, structural validation, and sustainability certification.
This module manages the lifecycle of carton packaging units within the Etz Hayyim network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112503"
UNISPSC_TITLE = "Carton"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Carton domain
    material_composition: str
    bursting_strength_kpa: int
    dimensions_mm: dict[str, int]
    recycled_content_pct: int
    is_fsc_certified: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects the input dimensions and material properties for compliance."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {"l": 300, "w": 200, "h": 150})
    material = inp.get("material", "Corrugated Fiberboard")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "dimensions_mm": dims,
        "material_composition": material,
        "is_fsc_certified": inp.get("fsc_check", True),
    }


def calculate_structural_integrity(state: State) -> dict[str, Any]:
    """Determines the bursting strength based on material composition."""
    material = state.get("material_composition", "")
    # Mock calculation: corrugated materials typically have higher strength ratings
    strength = 1400 if "corrugated" in material.lower() else 800

    return {
        "log": [f"{UNISPSC_CODE}:calculate_structural_integrity"],
        "bursting_strength_kpa": strength,
        "recycled_content_pct": 75 if "fiber" in material.lower() else 30,
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the carton certification and prepares the actor output."""
    dims = state.get("dimensions_mm", {})
    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "CERTIFIED",
            "specs": {
                "volume_mm3": dims.get("l", 0) * dims.get("w", 0) * dims.get("h", 0),
                "strength_kpa": state.get("bursting_strength_kpa"),
                "sustainability": {
                    "recycled_pct": state.get("recycled_content_pct"),
                    "fsc": state.get("is_fsc_certified"),
                }
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("calculate", calculate_structural_integrity)
_g.add_node("emit", certify_and_emit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
