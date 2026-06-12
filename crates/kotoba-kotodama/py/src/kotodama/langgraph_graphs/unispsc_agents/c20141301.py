# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141301 — Gear (segment 20).
Bespoke logic for mechanical gear specification and load validation in mining contexts.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141301"
UNISPSC_TITLE = "Gear"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Gear
    gear_material: str
    tooth_count: int
    pitch_diameter: float
    load_capacity_kn: float
    tolerance_verified: bool


def inspect_spec(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and material grade of the gear."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    teeth = int(inp.get("teeth", 24))
    diameter = float(inp.get("diameter", 150.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "gear_material": material,
        "tooth_count": teeth,
        "pitch_diameter": diameter,
        "tolerance_verified": diameter > 0 and teeth > 0,
    }


def calculate_load(state: State) -> dict[str, Any]:
    """Computes theoretical load capacity based on material and tooth count."""
    material_factor = 1.5 if state.get("gear_material") == "alloy_steel" else 1.0
    teeth = state.get("tooth_count", 0)
    diameter = state.get("pitch_diameter", 0.0)

    # Heuristic calculation for a mining-grade gear
    capacity = (teeth * diameter * material_factor) / 100.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load"],
        "load_capacity_kn": round(capacity, 2),
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final actor response with computed specifications."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specifications": {
                "material": state.get("gear_material"),
                "teeth": state.get("tooth_count"),
                "diameter_mm": state.get("pitch_diameter"),
                "capacity_kn": state.get("load_capacity_kn"),
            },
            "status": "certified" if state.get("tolerance_verified") else "pending_review",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("calculate_load", calculate_load)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "calculate_load")
_g.add_edge("calculate_load", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
