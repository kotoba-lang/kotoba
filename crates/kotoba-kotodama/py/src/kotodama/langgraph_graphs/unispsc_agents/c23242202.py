# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242202 — Hobbing (segment 23).

Bespoke implementation for gear generation via continuous indexing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242202"
UNISPSC_TITLE = "Hobbing"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242202"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Gear Hobbing
    geometry_specs: dict[str, Any]
    kinematic_ratio: float
    cutting_depth: float
    indexing_verified: bool


def validate_geometry(state: State) -> dict[str, Any]:
    """Validate gear teeth, module, and pressure angle requirements."""
    inp = state.get("input") or {}
    # Default to standard spur gear if not provided in input
    geo = inp.get("geometry", {"teeth": 32, "module": 2.0, "pressure_angle": 20.0})

    return {
        "log": [f"{UNISPSC_CODE}:validate_geometry: {geo.get('teeth')} teeth"],
        "geometry_specs": geo,
        "indexing_verified": geo.get("teeth", 0) > 0
    }


def calculate_kinematics(state: State) -> dict[str, Any]:
    """Calculate the change-gear ratio for hob-to-workpiece synchronization."""
    geo = state.get("geometry_specs", {})
    teeth = geo.get("teeth", 1)
    # Gear ratio for a single-start hob setup
    ratio = 1.0 / teeth if teeth > 0 else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_kinematics: ratio={ratio:.6f}"],
        "kinematic_ratio": ratio,
        "cutting_depth": geo.get("module", 2.0) * 2.25
    }


def generate_teeth(state: State) -> dict[str, Any]:
    """Simulate the generating motion to produce involute tooth forms."""
    ratio = state.get("kinematic_ratio", 0.0)
    depth = state.get("cutting_depth", 0.0)
    verified = state.get("indexing_verified", False)

    success = verified and ratio > 0 and depth > 0

    return {
        "log": [f"{UNISPSC_CODE}:generate_teeth: depth={depth:.3f}mm"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "process_metadata": {
                "ratio": ratio,
                "final_depth": depth,
                "indexing": "verified" if verified else "failed"
            },
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_geometry)
_g.add_node("kinematics", calculate_kinematics)
_g.add_node("generate", generate_teeth)

_g.add_edge(START, "validate")
_g.add_edge("validate", "kinematics")
_g.add_edge("kinematics", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
