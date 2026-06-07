# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142200 — Bearing (segment 20).
Bespoke logic for bearing specification validation and cataloging.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142200"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142200"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bearing domain state
    bearing_type: str
    radial_load_capacity: float
    material_spec: str
    is_lubricated: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects the mechanical specifications of the bearing."""
    inp = state.get("input") or {}
    b_type = inp.get("bearing_type", "ball_bearing")
    mat = inp.get("material", "carbon_steel")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "bearing_type": b_type,
        "material_spec": mat,
    }


def calculate_load_limits(state: State) -> dict[str, Any]:
    """Simulates calculating load limits based on bearing type and material."""
    b_type = state.get("bearing_type", "ball_bearing")
    # Simulation logic: roller bearings handle higher loads than ball bearings
    load = 5000.0 if "roller" in b_type.lower() else 2500.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_limits"],
        "radial_load_capacity": load,
        "is_lubricated": True,
    }


def issue_catalog_entry(state: State) -> dict[str, Any]:
    """Finalizes the catalog entry for the bearing actor."""
    load = state.get("radial_load_capacity", 0.0)
    b_type = state.get("bearing_type", "unknown")
    mat = state.get("material_spec", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:issue_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "bearing_profile": {
                "type": b_type,
                "material": mat,
                "load_rating_n": load,
                "is_active": True,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specs)
_g.add_node("calculate", calculate_load_limits)
_g.add_node("issue", issue_catalog_entry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calculate")
_g.add_edge("calculate", "issue")
_g.add_edge("issue", END)

graph = _g.compile()
