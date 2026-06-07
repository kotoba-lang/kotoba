# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112402 — Cabinet (segment 24).

Bespoke graph for cabinet material handling and storage equipment.
Processes dimensional verification, material selection, and security features.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112402"
UNISPSC_TITLE = "Cabinet"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112402"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for "Cabinet"
    dimensions_verified: bool
    material_grade: str
    locking_mechanism: str
    shelf_load_capacity_kg: int


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material requirements for the cabinet."""
    inp = state.get("input") or {}
    # Simulate dimension check logic
    width = inp.get("width_mm", 0)
    height = inp.get("height_mm", 0)
    valid_dims = width > 0 and height > 0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "dimensions_verified": valid_dims,
        "material_grade": inp.get("material", "Industrial Steel"),
    }


def configure_security(state: State) -> dict[str, Any]:
    """Determines the locking and safety configuration based on material and input."""
    material = state.get("material_grade", "Standard")
    # Higher grade materials get biometric or electronic locks in this logic
    lock_type = "Electronic Keypad" if "Steel" in material else "Manual Cam Lock"

    return {
        "log": [f"{UNISPSC_CODE}:configure_security"],
        "locking_mechanism": lock_type,
        "shelf_load_capacity_kg": 50 if "Steel" in material else 20,
    }


def emit_manifest(state: State) -> dict[str, Any]:
    """Generates the final storage equipment manifest and metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("material_grade"),
                "security": state.get("locking_mechanism"),
                "capacity": state.get("shelf_load_capacity_kg"),
                "verified": state.get("dimensions_verified"),
            },
            "status": "configured",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("configure_security", configure_security)
_g.add_node("emit_manifest", emit_manifest)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "configure_security")
_g.add_edge("configure_security", "emit_manifest")
_g.add_edge("emit_manifest", END)

graph = _g.compile()
