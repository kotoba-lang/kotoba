# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174105 — Rack (segment 25).

Bespoke graph logic for vehicle racks, handling specification verification,
safety certification simulation, and inventory data packaging.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174105"
UNISPSC_TITLE = "Rack"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174105"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for "Rack" (Vehicle components)
    load_capacity_kg: float
    mounting_type: str
    safety_certified: bool
    material_composition: str


def configure_rack(state: State) -> dict[str, Any]:
    """Extract and set initial rack configuration from input."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 75.0))
    m_type = str(inp.get("mounting", "Roof Rail"))

    return {
        "log": [f"{UNISPSC_CODE}:configure_rack"],
        "load_capacity_kg": capacity,
        "mounting_type": m_type,
        "material_composition": "Reinforced Aluminum Alloy",
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Simulate safety and stress testing for the rack configuration."""
    capacity = state.get("load_capacity_kg", 0.0)
    # Racks with capacity over 150kg require heavy-duty certification
    certified = capacity <= 200.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards"],
        "safety_certified": certified,
    }


def generate_inventory_record(state: State) -> dict[str, Any]:
    """Finalize the rack metadata and produce the result dictionary."""
    is_ok = state.get("safety_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "load_capacity": state.get("load_capacity_kg"),
                "mounting": state.get("mounting_type"),
                "material": state.get("material_composition"),
            },
            "status": "APPROVED" if is_ok else "REJECTED_SAFETY_LIMIT",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_rack)
_g.add_node("verify", verify_safety_standards)
_g.add_node("finalize", generate_inventory_record)

_g.add_edge(START, "configure")
_g.add_edge("configure", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
