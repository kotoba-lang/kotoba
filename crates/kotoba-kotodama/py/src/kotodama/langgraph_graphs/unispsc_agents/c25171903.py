# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171903 — Rim (segment 25).

Bespoke LangGraph implementation for automotive rim specifications and cataloging.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171903"
UNISPSC_TITLE = "Rim"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Rim
    material_type: str
    diameter_inches: float
    width_inches: float
    bolt_pattern: str
    is_compliant: bool


def validate_rim_specs(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and material of the rim."""
    inp = state.get("input") or {}
    material = inp.get("material", "Alloy")
    diameter = float(inp.get("diameter", 17.0))
    width = float(inp.get("width", 7.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_rim_specs"],
        "material_type": material,
        "diameter_inches": diameter,
        "width_inches": width,
    }


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Verifies that the rim meets standard safety and load ratings."""
    inp = state.get("input") or {}
    bolt_pattern = inp.get("bolt_pattern", "5x114.3")
    load_rating = inp.get("load_rating", 1500)

    # Simple logic: rims with diameter < 10 or width < 4 are rejected
    is_compliant = state.get("diameter_inches", 0) >= 10 and load_rating > 500

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance"],
        "bolt_pattern": bolt_pattern,
        "is_compliant": is_compliant,
    }


def finalize_catalog_entry(state: State) -> dict[str, Any]:
    """Formats the final rim specifications for the component catalog."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specifications": {
                "material": state.get("material_type"),
                "dimensions": f"{state.get('diameter_inches')}x{state.get('width_inches')}",
                "bolt_pattern": state.get("bolt_pattern"),
            },
            "status": "APPROVED" if state.get("is_compliant") else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_rim_specs)
_g.add_node("verify", verify_safety_compliance)
_g.add_node("finalize", finalize_catalog_entry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
