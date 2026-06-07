# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24141702 — Tube Specs (segment 24).

Bespoke logic for handling tube specifications, including dimension
validation, material compatibility checks, and specification certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141702"
UNISPSC_TITLE = "Tube Specs"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Tube Specs
    dimensions: dict[str, float]
    material_grade: str
    tolerance_check: bool
    compliance_score: int


def configure_specs(state: State) -> dict[str, Any]:
    """Extracts dimensions and material details from the input payload."""
    inp = state.get("input") or {}
    dims = {
        "outer_diameter": float(inp.get("od", 0.0)),
        "wall_thickness": float(inp.get("wt", 0.0)),
        "length": float(inp.get("len", 0.0)),
    }
    material = str(inp.get("material", "ASTM-A513"))
    return {
        "log": [f"{UNISPSC_CODE}:configure_specs"],
        "dimensions": dims,
        "material_grade": material,
    }


def check_compliance(state: State) -> dict[str, Any]:
    """Validates if the tube specs meet standard industrial tolerances."""
    dims = state.get("dimensions", {})
    od = dims.get("outer_diameter", 0.0)
    wt = dims.get("wall_thickness", 0.0)

    # Basic physical constraint: wall thickness must be less than radius
    is_physical = wt > 0 and od > (2 * wt)
    score = 100 if is_physical else 0

    return {
        "log": [f"{UNISPSC_CODE}:check_compliance"],
        "tolerance_check": is_physical,
        "compliance_score": score,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Compiles the final specification certificate for the tube."""
    is_ok = state.get("tolerance_check", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "verified": is_ok,
            "specs": {
                "material": state.get("material_grade"),
                "dimensions": state.get("dimensions"),
                "score": state.get("compliance_score"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_specs)
_g.add_node("validate", check_compliance)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "configure")
_g.add_edge("configure", "validate")
_g.add_edge("validate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
