# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251808"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251808"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mandrel_diameter: float
    bend_radius: float
    material_hardness: str
    integrity_verified: bool
    lubrication_active: bool


def validate_mandrel_specs(state: State) -> dict[str, Any]:
    """Validates technical dimensions for the pipe bending mandrel."""
    inp = state.get("input") or {}
    diameter = inp.get("diameter", 45.0)
    radius = inp.get("radius", 135.0)
    hardness = inp.get("hardness", "high-tensile")

    return {
        "log": [f"{UNISPSC_CODE}:validate_mandrel_specs"],
        "mandrel_diameter": float(diameter),
        "bend_radius": float(radius),
        "material_hardness": hardness,
    }


def perform_integrity_check(state: State) -> dict[str, Any]:
    """Simulates a structural inspection and lubrication check."""
    diameter = state.get("mandrel_diameter", 0.0)
    # Mandrel must have a positive diameter to be valid
    is_valid = diameter > 0.1

    return {
        "log": [f"{UNISPSC_CODE}:perform_integrity_check"],
        "integrity_verified": is_valid,
        "lubrication_active": True if is_valid else False,
    }


def finalize_tooling_status(state: State) -> dict[str, Any]:
    """Finalizes the mandrel state for the manufacturing process."""
    verified = state.get("integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_tooling_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "diameter_mm": state.get("mandrel_diameter"),
                "radius_mm": state.get("bend_radius"),
                "hardness": state.get("material_hardness"),
                "lubricated": state.get("lubrication_active"),
            },
            "ready_for_production": verified,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_mandrel_specs)
_g.add_node("inspect", perform_integrity_check)
_g.add_node("finalize", finalize_tooling_status)

_g.add_edge(START, "validate")
_g.add_edge("validate", "inspect")
_g.add_edge("inspect", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
