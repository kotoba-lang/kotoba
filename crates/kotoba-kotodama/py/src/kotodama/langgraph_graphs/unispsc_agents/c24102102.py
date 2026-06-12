# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102102 — Carousel (segment 24).
Bespoke logic for automated storage and retrieval carousel systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102102"
UNISPSC_TITLE = "Carousel"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Carousel operation
    target_bin_index: int
    rotation_direction: str
    load_weight_kg: float
    proximity_sensor_active: bool


def inventory_lookup(state: State) -> dict[str, Any]:
    """Determines the physical location of the requested inventory item."""
    inp = state.get("input") or {}
    item_id = str(inp.get("sku", "GENERAL"))
    # Deterministic mapping for simulation: SKU characters determine bin index
    bin_idx = sum(ord(c) for c in item_id) % 50
    weight = float(inp.get("weight", 10.5))

    return {
        "log": [f"{UNISPSC_CODE}:inventory_lookup:sku={item_id}:bin={bin_idx}"],
        "target_bin_index": bin_idx,
        "load_weight_kg": weight,
    }


def rotation_sequence(state: State) -> dict[str, Any]:
    """Calculates the shortest path for the carousel to rotate to the target bin."""
    target = state.get("target_bin_index", 0)
    # Assuming a 50-bin carousel, determine if Clockwise or Counter-Clockwise is shorter
    direction = "CLOCKWISE" if target <= 25 else "COUNTER_CLOCKWISE"

    return {
        "log": [f"{UNISPSC_CODE}:rotation_sequence:dir={direction}"],
        "rotation_direction": direction,
        "proximity_sensor_active": True,
    }


def extract_item(state: State) -> dict[str, Any]:
    """Finalizes the retrieval process and verifies safety/weight constraints."""
    weight = state.get("load_weight_kg", 0.0)
    # Safety check: Carousels have per-bin and total structural weight limits
    authorized = weight < 150.0

    return {
        "log": [f"{UNISPSC_CODE}:extract_item:authorized={authorized}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "bin_index": state.get("target_bin_index"),
            "weight_valid": authorized,
            "status": "ITEM_READY" if authorized else "SAFETY_HALT_OVERWEIGHT",
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)
_g.add_node("inventory_lookup", inventory_lookup)
_g.add_node("rotation_sequence", rotation_sequence)
_g.add_node("extract_item", extract_item)

_g.add_edge(START, "inventory_lookup")
_g.add_edge("inventory_lookup", "rotation_sequence")
_g.add_edge("rotation_sequence", "extract_item")
_g.add_edge("extract_item", END)

graph = _g.compile()
