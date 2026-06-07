# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20111617 — Connector (segment 20).

Bespoke logic for managing connector specification and material validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20111617"
UNISPSC_TITLE = "Connector"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20111617"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for "Connector"
    connector_type: str
    pin_count: int
    shielding_required: bool
    material_compatibility: list[str]


def analyze_spec(state: State) -> dict[str, Any]:
    """Analyzes the connector specification from input."""
    inp = state.get("input") or {}
    c_type = inp.get("type", "standard-io")
    pins = int(inp.get("pins", 4))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_spec"],
        "connector_type": c_type,
        "pin_count": pins,
        "shielding_required": pins > 8 or "high-speed" in c_type.lower()
    }


def validate_materials(state: State) -> dict[str, Any]:
    """Determines compatible materials based on environment and type."""
    c_type = state.get("connector_type", "standard-io")
    materials = ["brass", "thermoplastic"]

    if state.get("shielding_required"):
        materials.append("nickel-plating")
    if "industrial" in c_type.lower():
        materials.append("stainless-steel")

    return {
        "log": [f"{UNISPSC_CODE}:validate_materials"],
        "material_compatibility": materials
    }


def finalize_catalog_entry(state: State) -> dict[str, Any]:
    """Compiles the final product record for the connector."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "type": state.get("connector_type"),
                "pins": state.get("pin_count"),
                "shielding": state.get("shielding_required"),
                "approved_materials": state.get("material_compatibility"),
            },
            "status": "validated",
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_spec)
_g.add_node("validate", validate_materials)
_g.add_node("finalize", finalize_catalog_entry)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "validate")
_g.add_edge("validate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
