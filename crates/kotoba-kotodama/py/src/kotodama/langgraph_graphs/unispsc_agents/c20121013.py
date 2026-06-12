# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121013 — Bearing (segment 20).

Bespoke logic for managing mechanical bearing specifications and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121013"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121013"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bearing
    bearing_type: str
    load_capacity_kn: float
    dimensions_verified: bool
    lubrication_spec: str


def inspect_specs(state: State) -> dict[str, Any]:
    """Validates physical dimensions and bearing classification."""
    inp = state.get("input") or {}
    b_type = inp.get("type", "Deep Groove Ball")
    dims = inp.get("dimensions", {})
    # Check for essential mechanical dimensions
    verified = all(k in dims for k in ["inner_diameter", "outer_diameter", "width"])

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "bearing_type": b_type,
        "dimensions_verified": verified,
    }


def assess_load(state: State) -> dict[str, Any]:
    """Evaluates the load capacity based on material and design specs."""
    inp = state.get("input") or {}
    # Simulate extraction of dynamic load rating
    capacity = inp.get("dynamic_load_rating", 12.7)
    lubrication = inp.get("lubrication", "Lithium Base Grease")

    return {
        "log": [f"{UNISPSC_CODE}:assess_load"],
        "load_capacity_kn": capacity,
        "lubrication_spec": lubrication,
    }


def certify_component(state: State) -> dict[str, Any]:
    """Finalizes the bearing validation and issues the actor result."""
    is_ready = state.get("dimensions_verified", False) and state.get("load_capacity_kn", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:certify_component"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "meta": {
                "bearing_type": state.get("bearing_type"),
                "load_rating_kn": state.get("load_capacity_kn"),
                "lubrication": state.get("lubrication_spec"),
                "compliance": is_ready
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("assess_load", assess_load)
_g.add_node("certify_component", certify_component)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "assess_load")
_g.add_edge("assess_load", "certify_component")
_g.add_edge("certify_component", END)

graph = _g.compile()
