# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121500 — Packaging (segment 24).

Bespoke graph for packaging specifications, material selection, and integrity verification.
This agent handles state transitions for defining packaging requirements and ensuring
compliance with material durability and sustainability standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121500"
UNISPSC_TITLE = "Packaging"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Packaging
    material_type: str
    dimensions_mm: dict[str, float]
    weight_limit_kg: float
    is_recyclable: bool
    integrity_verified: bool


def configure_specs(state: State) -> dict[str, Any]:
    """Node: Parse input for packaging dimensions and weight limits."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {"length": 100.0, "width": 100.0, "height": 100.0})
    weight = inp.get("max_weight", 5.0)
    return {
        "log": [f"{UNISPSC_CODE}:configure_specs"],
        "dimensions_mm": dims,
        "weight_limit_kg": weight,
    }


def select_materials(state: State) -> dict[str, Any]:
    """Node: Determine appropriate material based on weight and eco-requirements."""
    weight = state.get("weight_limit_kg", 0.0)

    if weight > 20.0:
        material = "Reinforced Wood Crate"
        recyclable = False
    elif weight > 5.0:
        material = "Double-Wall Corrugated Fiberboard"
        recyclable = True
    else:
        material = "Recycled Kraft Paperboard"
        recyclable = True

    return {
        "log": [f"{UNISPSC_CODE}:select_materials"],
        "material_type": material,
        "is_recyclable": recyclable,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Node: Finalize the packaging manifest and verify structural integrity."""
    material = state.get("material_type", "Unknown")
    recyclable = state.get("is_recyclable", False)

    # Simple logic: wood crates and corrugated fiberboard pass by default in this simulation
    verified = any(m in material for m in ["Crate", "Corrugated", "Paperboard"])

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "integrity_verified": verified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": material,
                "recyclable": recyclable,
                "integrity_check": "PASSED" if verified else "FAILED",
            },
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_specs)
_g.add_node("select", select_materials)
_g.add_node("verify", verify_integrity)

_g.add_edge(START, "configure")
_g.add_edge("configure", "select")
_g.add_edge("select", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
