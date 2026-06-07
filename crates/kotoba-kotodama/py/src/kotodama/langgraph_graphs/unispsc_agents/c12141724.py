# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141724 — Adsorbent (segment 12).

This module provides bespoke logic for modeling and processing adsorbent
materials, focusing on physical properties like surface area and adsorption
capacity.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141724"
UNISPSC_TITLE = "Adsorbent"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141724"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Adsorbent
    surface_area: float
    pore_volume: float
    material_type: str
    saturation_point: float


def inspect_material(state: State) -> dict[str, Any]:
    """Inspects the adsorbent material properties from input."""
    inp = state.get("input") or {}
    surface_area = float(inp.get("surface_area", 500.0))
    material_type = str(inp.get("material_type", "activated_carbon"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "surface_area": surface_area,
        "material_type": material_type,
    }


def calculate_capacity(state: State) -> dict[str, Any]:
    """Simulates adsorption capacity based on surface area."""
    # Simple heuristic for demonstration: capacity scales with surface area
    sa = state.get("surface_area", 0.0)
    pore_volume = sa * 0.0012  # Simplified ratio (cm3/g)
    saturation_point = sa * 0.5  # Simplified capacity (mg/g)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_capacity"],
        "pore_volume": pore_volume,
        "saturation_point": saturation_point,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Finalizes the adsorbent specification report."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "properties": {
                "material": state.get("material_type"),
                "surface_area_m2g": state.get("surface_area"),
                "pore_volume_cm3g": state.get("pore_volume"),
                "max_saturation_mgg": state.get("saturation_point"),
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_material", inspect_material)
_g.add_node("calculate_capacity", calculate_capacity)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "inspect_material")
_g.add_edge("inspect_material", "calculate_capacity")
_g.add_edge("calculate_capacity", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
