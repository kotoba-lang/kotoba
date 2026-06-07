# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102103 — Casing (segment 24).
Bespoke implementation for material handling and structural casing logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102103"
UNISPSC_TITLE = "Casing"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102103"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    casing_material: str
    load_capacity_kg: float
    wall_thickness_mm: float
    integrity_verified: bool
    compliance_standard: str


def analyze_requirements(state: State) -> dict[str, Any]:
    """Extracts and analyzes casing requirements from input parameters."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:analyze_requirements"],
        "casing_material": inp.get("material", "Reinforced Steel"),
        "load_capacity_kg": float(inp.get("max_load", 1500.0)),
        "wall_thickness_mm": float(inp.get("thickness", 5.5)),
    }


def verify_structural_integrity(state: State) -> dict[str, Any]:
    """Validates if the casing specifications meet industrial safety standards."""
    load = state.get("load_capacity_kg", 0)
    thickness = state.get("wall_thickness_mm", 0)

    # Simple logic: higher loads require thicker walls
    is_safe = (load < 1000 and thickness >= 3.0) or (load >= 1000 and thickness >= 5.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_structural_integrity"],
        "integrity_verified": is_safe,
        "compliance_standard": "ISO-2410-MATERIAL-HANDLING",
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Produces the final result manifest for the casing unit."""
    verified = state.get("integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": verified,
            "details": {
                "material": state.get("casing_material"),
                "capacity": state.get("load_capacity_kg"),
                "standard": state.get("compliance_standard"),
            },
            "status": "PASS" if verified else "FAIL"
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_requirements)
_g.add_node("verify", verify_structural_integrity)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
