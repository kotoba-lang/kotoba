# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121502"
UNISPSC_TITLE = "Pallet"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Pallet management
    material: str  # e.g., wood, plastic, metal, corrugated paper
    load_capacity_kg: float
    is_safety_checked: bool
    current_occupancy: float
    inventory_location: str


def inspect_integrity(state: State) -> dict[str, Any]:
    """Inspects the physical integrity and material specifications of the pallet."""
    inp = state.get("input") or {}
    material = inp.get("material", "wood")

    # Standard capacities based on material
    capacities = {
        "wood": 1200.0,
        "plastic": 1500.0,
        "metal": 2500.0,
        "corrugated": 400.0
    }

    return {
        "log": [f"{UNISPSC_CODE}:inspect_integrity"],
        "material": material,
        "load_capacity_kg": capacities.get(material.lower(), 1000.0),
        "is_safety_checked": True,
    }


def validate_load(state: State) -> dict[str, Any]:
    """Validates if the requested load exceeds the pallet's safety capacity."""
    inp = state.get("input") or {}
    weight = float(inp.get("target_weight", 0.0))
    limit = state.get("load_capacity_kg", 0.0)

    within_limits = weight <= limit
    location = "ZONE_A" if within_limits else "REJECT_BAY"

    return {
        "log": [f"{UNISPSC_CODE}:validate_load"],
        "current_occupancy": weight if within_limits else 0.0,
        "inventory_location": location,
    }


def record_manifest(state: State) -> dict[str, Any]:
    """Finalizes the pallet record and prepares the output result."""
    is_ok = state.get("inventory_location") != "REJECT_BAY"

    return {
        "log": [f"{UNISPSC_CODE}:record_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "material": state.get("material"),
            "load_status": "allocated" if is_ok else "failed_capacity_check",
            "location": state.get("inventory_location"),
            "verified": state.get("is_safety_checked", False),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_integrity)
_g.add_node("validate", validate_load)
_g.add_node("record", record_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "validate")
_g.add_edge("validate", "record")
_g.add_edge("record", END)

graph = _g.compile()
