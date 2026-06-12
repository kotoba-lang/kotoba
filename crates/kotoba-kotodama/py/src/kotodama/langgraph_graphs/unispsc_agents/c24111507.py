# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111507 — Tool Bag (segment 24).

Bespoke graph logic for tool bag material validation and specification
verification. This agent handles the lifecycle of a tool bag design
from initial specification to final catalog manifest.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111507"
UNISPSC_TITLE = "Tool Bag"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111507"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Tool Bag
    material_type: str
    pocket_count: int
    is_weatherproof: bool
    capacity_liters: float


def inspect_materials(state: State) -> dict[str, Any]:
    """Inspects the input for material specifications and pocket configurations."""
    inp = state.get("input") or {}
    material = inp.get("material", "Heavy-duty Nylon")
    pockets = inp.get("pockets", 12)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_materials -> {material}"],
        "material_type": material,
        "pocket_count": pockets,
    }


def verify_durability(state: State) -> dict[str, Any]:
    """Calculates reinforcement needs and weatherproofing status."""
    material = state.get("material_type", "Nylon")

    # Logic to determine reinforcement and weatherproofing
    is_weatherproof = "nylon" in material.lower() or "canvas" in material.lower()
    capacity = 18.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_durability -> weatherproof={is_weatherproof}"],
        "is_weatherproof": is_weatherproof,
        "capacity_liters": capacity,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Assembles the final Tool Bag catalog entry with all verified specs."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "material": state.get("material_type"),
                "pockets": state.get("pocket_count"),
                "weatherproof": state.get("is_weatherproof"),
                "volume": f"{state.get('capacity_liters')}L",
            },
            "status": "ready_for_distribution",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_materials", inspect_materials)
_g.add_node("verify_durability", verify_durability)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_materials")
_g.add_edge("inspect_materials", "verify_durability")
_g.add_edge("verify_durability", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
