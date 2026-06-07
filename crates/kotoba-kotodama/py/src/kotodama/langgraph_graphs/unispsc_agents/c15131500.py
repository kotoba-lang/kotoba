# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15131500 — Material (segment 15).

Bespoke graph logic for handling material specifications, quality grading,
and inventory verification within the UNISPSC 15 segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15131500"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15131500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Material
    material_type: str
    quality_standard: str
    stock_confirmed: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Inspects the input for material details and assigns a type."""
    inp = state.get("input") or {}
    m_type = inp.get("type", "industrial")
    standard = inp.get("standard", "ISO-9001")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "material_type": m_type,
        "quality_standard": standard,
    }


def verify_quality(state: State) -> dict[str, Any]:
    """Verifies if the material meets the quality standards."""
    standard = state.get("quality_standard", "N/A")
    # Pure Python logic: assume all specific standards pass for simulation
    passed = standard.startswith("ISO") or standard == "ASTM"
    return {
        "log": [f"{UNISPSC_CODE}:verify_quality:{passed}"],
        "stock_confirmed": passed,
    }


def catalog_entry(state: State) -> dict[str, Any]:
    """Finalizes the material record for the catalog."""
    return {
        "log": [f"{UNISPSC_CODE}:catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material_type": state.get("material_type"),
            "quality_standard": state.get("quality_standard"),
            "verified": state.get("stock_confirmed", False),
            "outcome": "cataloged",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_material)
_g.add_node("verify", verify_quality)
_g.add_node("catalog", catalog_entry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "catalog")
_g.add_edge("catalog", END)

graph = _g.compile()
