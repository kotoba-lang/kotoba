# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for UNISPSC 24112108: Drum.
Handles container specification validation, integrity inspection, and inventory logging.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112108"
UNISPSC_TITLE = "Drum"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112108"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Drum
    material: str  # Steel, Plastic, Fiber
    capacity_liters: float
    seal_type: str  # Open-head, Tight-head
    integrity_check: bool
    is_hazardous_rated: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the physical specifications of the drum container."""
    inp = state.get("input") or {}
    material = inp.get("material", "Steel")
    capacity = float(inp.get("capacity", 208.0))  # Default to standard 55-gallon (208L)
    is_haz = inp.get("hazardous_rated", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "material": material,
        "capacity_liters": capacity,
        "is_hazardous_rated": is_haz,
    }


def inspect_integrity(state: State) -> dict[str, Any]:
    """Simulates a quality control check on the drum's seal and structural integrity."""
    # Logic: Hazardous drums require stricter seal checks
    is_haz = state.get("is_hazardous_rated", False)
    seal = "Tight-head" if is_haz else state.get("input", {}).get("seal", "Open-head")

    # In a pure-Python simulation, we assume passing integrity if material is recognized
    passed = state.get("material") in ["Steel", "Plastic", "Fiber"]

    return {
        "log": [f"{UNISPSC_CODE}:inspect_integrity"],
        "seal_type": seal,
        "integrity_check": passed,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes the drum record for material handling systems."""
    is_ok = state.get("integrity_check", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "specs": {
            "material": state.get("material"),
            "capacity": state.get("capacity_liters"),
            "seal": state.get("seal_type"),
        },
        "verified": is_ok,
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("validate_specification", validate_specification)
_g.add_node("inspect_integrity", inspect_integrity)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "inspect_integrity")
_g.add_edge("inspect_integrity", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
