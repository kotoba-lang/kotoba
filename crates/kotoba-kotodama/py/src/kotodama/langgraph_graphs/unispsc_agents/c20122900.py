# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122900 — Drilling Part (segment 20).

Bespoke logic for managing drilling component lifecycle and integrity checks.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122900"
UNISPSC_TITLE = "Drilling Part"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    material_hardness_rockwell: float
    depth_rating_meters: int
    inspection_passed: bool
    component_type: str


def validate_metallurgy(state: State) -> dict[str, Any]:
    """Inspects the material properties of the drilling part."""
    inp = state.get("input") or {}
    hardness = float(inp.get("hardness", 45.0))
    comp_type = inp.get("type", "generic_drill_bit")

    return {
        "log": [f"{UNISPSC_CODE}:validate_metallurgy"],
        "material_hardness_rockwell": hardness,
        "component_type": comp_type,
        "inspection_passed": hardness >= 40.0,
    }


def assess_operational_limit(state: State) -> dict[str, Any]:
    """Calculates safe operating depth based on material and type."""
    hardness = state.get("material_hardness_rockwell", 0.0)
    # Heuristic: harder materials rated for deeper high-pressure environments
    depth = int(hardness * 100)

    return {
        "log": [f"{UNISPSC_CODE}:assess_operational_limit"],
        "depth_rating_meters": depth,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Emits the certified drilling part data."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "type": state.get("component_type"),
                "hardness_hrc": state.get("material_hardness_rockwell"),
                "max_depth": state.get("depth_rating_meters"),
                "certified": state.get("inspection_passed"),
            },
            "status": "ready_for_deployment" if state.get("inspection_passed") else "quarantined",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_metallurgy)
_g.add_node("assess", assess_operational_limit)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
