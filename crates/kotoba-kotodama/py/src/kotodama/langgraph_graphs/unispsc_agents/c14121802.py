# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121802 — File Folder (segment 14).

Bespoke graph implementation for managing File Folder specifications,
material selection, and capacity calculations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121802"
UNISPSC_TITLE = "File Folder"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_type: str
    tab_cut: str
    expansion_capacity: float
    reinforced_tabs: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the input material and tab configuration for the folder."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "manila"))
    tab = str(inp.get("tab_cut", "1/3-cut"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material_type": material,
        "tab_cut": tab,
    }


def calculate_dimensions(state: State) -> dict[str, Any]:
    """Determines expansion capacity based on folder material type."""
    material = state.get("material_type", "manila")
    # Higher grade materials like pressboard allow for larger expansion
    expansion = 2.0 if material.lower() == "pressboard" else 0.75

    return {
        "log": [f"{UNISPSC_CODE}:calculate_dimensions"],
        "expansion_capacity": expansion,
        "reinforced_tabs": expansion > 1.0,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Compiles the final folder asset record."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attributes": {
                "material": state.get("material_type"),
                "tab_cut": state.get("tab_cut"),
                "expansion_inches": state.get("expansion_capacity"),
                "is_reinforced": state.get("reinforced_tabs"),
            },
            "compliance": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("calculate", calculate_dimensions)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
