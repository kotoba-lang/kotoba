# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101900 — Drum Handling (segment 24).

Bespoke graph logic for managing drum handling operations, including
physical inspection, load logistics evaluation, and dispatch confirmation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101900"
UNISPSC_TITLE = "Drum Handling"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Drum Handling domain fields
    drum_material: str
    gross_weight: float
    handling_equipment: str
    safety_protocol_active: bool


def inspect_unit(state: State) -> dict[str, Any]:
    """Analyzes the physical characteristics and hazards of the drum unit."""
    inp = state.get("input") or {}
    material = inp.get("material", "Steel")
    is_hazardous = inp.get("hazardous", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_unit -> {material}"],
        "drum_material": material,
        "safety_protocol_active": is_hazardous,
    }


def evaluate_logistics(state: State) -> dict[str, Any]:
    """Determines weight distribution and selects appropriate mechanical lifting equipment."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 205.0))
    material = state.get("drum_material")

    # Logic for selecting handling device based on material and weight
    if material == "Plastic":
        equipment = "Forks with Drum Snatcher"
    elif weight > 400:
        equipment = "Heavy-Duty Hydraulic Clamp"
    else:
        equipment = "Standard Vertical Drum Lifter"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_logistics -> {weight}kg using {equipment}"],
        "gross_weight": weight,
        "handling_equipment": equipment,
    }


def confirm_dispatch(state: State) -> dict[str, Any]:
    """Finalizes the handling procedure and prepares the result output."""
    material = state.get("drum_material")
    equip = state.get("handling_equipment")
    safety = state.get("safety_protocol_active")

    return {
        "log": [f"{UNISPSC_CODE}:confirm_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material": material,
            "equipment": equip,
            "safety_warning": "High Priority" if safety else "Standard",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_unit", inspect_unit)
_g.add_node("evaluate_logistics", evaluate_logistics)
_g.add_node("confirm_dispatch", confirm_dispatch)

_g.add_edge(START, "inspect_unit")
_g.add_edge("inspect_unit", "evaluate_logistics")
_g.add_edge("evaluate_logistics", "confirm_dispatch")
_g.add_edge("confirm_dispatch", END)

graph = _g.compile()
