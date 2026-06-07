# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122817 — Bearing (segment 20).

Bespoke logic for mechanical bearing component lifecycle, load analysis, and
specification validation within the Etz Hayyim supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122817"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122817"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Bearing mechanical components
    bearing_type: str
    load_capacity_kn: float
    material_spec: str
    lubrication_requirement: str
    is_certified: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the base mechanical specifications of the bearing."""
    inp = state.get("input") or {}
    b_type = inp.get("bearing_type", "deep_groove_ball")
    material = inp.get("material", "high_carbon_chromium_steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "bearing_type": b_type,
        "material_spec": material,
        "is_certified": False
    }


def calculate_load_dynamics(state: State) -> dict[str, Any]:
    """Calculates theoretical load ratings and lubrication needs."""
    # Simulation of mechanical analysis logic
    b_type = state.get("bearing_type", "")
    base_load = 25.0 if "roller" in b_type.lower() else 12.5

    # Heuristic for lubrication
    lubrication = "synthetic_grease" if base_load > 20 else "lithium_soap_grease"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_dynamics"],
        "load_capacity_kn": base_load,
        "lubrication_requirement": lubrication
    }


def emit_component_data(state: State) -> dict[str, Any]:
    """Finalizes the component state and emits the structured response."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_component_data"],
        "is_certified": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification_summary": {
                "type": state.get("bearing_type"),
                "material": state.get("material_spec"),
                "dynamic_load_kn": state.get("load_capacity_kn"),
                "lubrication": state.get("lubrication_requirement")
            },
            "status": "ready_for_procurement",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("calculate_load_dynamics", calculate_load_dynamics)
_g.add_node("emit_component_data", emit_component_data)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "calculate_load_dynamics")
_g.add_edge("calculate_load_dynamics", "emit_component_data")
_g.add_edge("emit_component_data", END)

graph = _g.compile()
