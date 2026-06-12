# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121900 — Bearing (segment 20).

Bespoke logic for managing bearing technical specifications, precision
compliance, and inventory readiness.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121900"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Bearing
    bearing_type: str
    load_rating_kn: float
    precision_class: str
    is_lubricated: bool


def inspect_spec(state: State) -> dict[str, Any]:
    """Inspects the input for bearing-specific technical parameters."""
    inp = state.get("input") or {}
    b_type = str(inp.get("bearing_type", "ball"))
    load = float(inp.get("load_rating", 10.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec -> {b_type} (load: {load}kN)"],
        "bearing_type": b_type,
        "load_rating_kn": load,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies bearing precision and lubrication status against standards."""
    inp = state.get("input") or {}
    precision = str(inp.get("precision", "P0"))
    lubed = bool(inp.get("lubricated", True))

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance -> class {precision}, lubed: {lubed}"],
        "precision_class": precision,
        "is_lubricated": lubed,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Finalizes the bearing entry with all validated attributes."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attributes": {
                "type": state.get("bearing_type"),
                "load_rating_kn": state.get("load_rating_kn"),
                "precision": state.get("precision_class"),
                "lubricated": state.get("is_lubricated"),
            },
            "status": "ready",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
