# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242601 — Beveling Graph (segment 23).
Bespoke implementation for industrial beveling machinery and edge preparation logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242601"
UNISPSC_TITLE = "Beveling Graph"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific beveling state
    bevel_angle: float
    material_type: str
    edge_profile: str
    pass_count: int
    coolant_flow_rate: float


def configure_geometry(state: State) -> dict[str, Any]:
    """Extracts and validates beveling geometry from input parameters."""
    inp = state.get("input") or {}
    angle = float(inp.get("angle", 30.0))
    profile = str(inp.get("profile", "V-Bevel"))

    return {
        "log": [f"{UNISPSC_CODE}:configure_geometry"],
        "bevel_angle": angle,
        "edge_profile": profile,
        "material_type": inp.get("material", "Carbon Steel"),
    }


def optimize_tooling(state: State) -> dict[str, Any]:
    """Determines pass count and coolant requirements based on material and angle."""
    angle = state.get("bevel_angle", 0.0)
    material = state.get("material_type", "")

    # Higher angles or harder materials require more passes
    passes = 1
    if angle > 45.0 or material.lower() == "stainless":
        passes = 3

    return {
        "log": [f"{UNISPSC_CODE}:optimize_tooling"],
        "pass_count": passes,
        "coolant_flow_rate": 5.5 if passes > 1 else 0.0,
    }


def validate_trajectory(state: State) -> dict[str, Any]:
    """Finalizes the beveling plan and formats the output result."""
    return {
        "log": [f"{UNISPSC_CODE}:validate_trajectory"],
        "result": {
            "status": "OPERATIONAL",
            "parameters": {
                "angle": state.get("bevel_angle"),
                "profile": state.get("edge_profile"),
                "passes": state.get("pass_count"),
                "coolant": state.get("coolant_flow_rate"),
            },
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "did": UNISPSC_DID,
            },
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_geometry)
_g.add_node("optimize", optimize_tooling)
_g.add_node("validate", validate_trajectory)

_g.add_edge(START, "configure")
_g.add_edge("configure", "optimize")
_g.add_edge("optimize", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
