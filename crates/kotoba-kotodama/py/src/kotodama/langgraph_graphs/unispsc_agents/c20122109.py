# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122109 — Belt (segment 20).

Bespoke graph logic for industrial belts used in mining and well drilling operations.
This agent handles specification validation, durability assessment, and
certification logging for heavy-duty power transmission and safety belts.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122109"
UNISPSC_TITLE = "Belt"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122109"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Belt (Mining/Drilling context)
    belt_material: str
    tensile_rating_kn: float
    is_flame_retardant: bool
    dimensions_verified: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical and safety specifications of the industrial belt."""
    inp = state.get("input") or {}
    material = inp.get("material", "Unknown Synthetic")
    tensile = float(inp.get("tensile_strength", 0.0))
    flame_ret = bool(inp.get("msha_certified", False))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "belt_material": material,
        "tensile_rating_kn": tensile,
        "is_flame_retardant": flame_ret,
        "dimensions_verified": "width" in inp and "length" in inp,
    }


def assess_industrial_suitability(state: State) -> dict[str, Any]:
    """Evaluates if the belt meets Segment 20 (Mining/Drilling) operational standards."""
    is_suitable = state.get("tensile_rating_kn", 0) > 50.0 and state.get("is_flame_retardant", False)
    suitability_msg = "PASSED" if is_suitable else "CONDITIONAL_APPROVAL"

    return {
        "log": [f"{UNISPSC_CODE}:assess_suitability - {suitability_msg}"]
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compiles the final asset metadata and result state."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("belt_material"),
                "tensile_kn": state.get("tensile_rating_kn"),
                "flame_retardant": state.get("is_flame_retardant"),
                "verified": state.get("dimensions_verified")
            },
            "ok": state.get("dimensions_verified", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("assess", assess_industrial_suitability)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
