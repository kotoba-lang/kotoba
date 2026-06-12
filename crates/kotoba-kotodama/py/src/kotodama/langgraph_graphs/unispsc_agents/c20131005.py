# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131005 — Drill Bit (segment 20).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131005"
UNISPSC_TITLE = "Drill Bit"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Drill Bit
    bit_type: str
    diameter_mm: float
    shank_type: str
    target_material: str
    is_verified: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Checks the input for drill bit geometry and intended use."""
    inp = state.get("input") or {}
    diameter = float(inp.get("diameter", 0.0))
    bit_type = str(inp.get("type", "twist"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "diameter_mm": diameter,
        "bit_type": bit_type,
        "is_verified": diameter > 0,
    }


def determine_manufacturing_params(state: State) -> dict[str, Any]:
    """Determines material and shank requirements based on bit type."""
    bit_type = state.get("bit_type", "twist")
    diameter = state.get("diameter_mm", 0.0)

    # Logic for drill bit characteristics
    shank = "Straight"
    if diameter > 13.0:
        shank = "Reduced"
    elif bit_type == "masonry":
        shank = "SDS-plus"

    target_material = "General Purpose"
    if bit_type == "brad_point":
        target_material = "Wood"
    elif bit_type == "masonry":
        target_material = "Concrete/Brick"

    return {
        "log": [f"{UNISPSC_CODE}:determine_manufacturing_params"],
        "shank_type": shank,
        "target_material": target_material,
    }


def generate_technical_data_sheet(state: State) -> dict[str, Any]:
    """Compiles the final drill bit specification into the result."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_technical_data_sheet"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specifications": {
                "type": state.get("bit_type"),
                "diameter": state.get("diameter_mm"),
                "shank": state.get("shank_type"),
                "application": state.get("target_material")
            },
            "validation_status": "PASS" if state.get("is_verified") else "FAIL"
        }
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("params", determine_manufacturing_params)
_g.add_node("finalize", generate_technical_data_sheet)

_g.add_edge(START, "validate")
_g.add_edge("validate", "params")
_g.add_edge("params", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
