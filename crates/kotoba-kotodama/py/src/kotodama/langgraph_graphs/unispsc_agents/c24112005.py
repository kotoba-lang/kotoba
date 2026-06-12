# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112005 — Basket (segment 24).

Bespoke LangGraph implementation for container management, focusing on
structural validation and capacity assessment for Basket assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112005"
UNISPSC_TITLE = "Basket"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112005"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for material handling baskets
    material: str
    volume_liters: float
    is_stackable: bool
    is_collapsible: bool
    integrity_certified: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects the physical specifications of the basket."""
    inp = state.get("input") or {}
    material = inp.get("material", "steel_wire")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "material": material,
        "integrity_certified": material in ["steel_wire", "plastic", "wicker"],
    }


def evaluate_capacity(state: State) -> dict[str, Any]:
    """Evaluates the storage capacity and nesting properties."""
    inp = state.get("input") or {}
    volume = float(inp.get("volume", 45.0))
    stackable = inp.get("stackable", True)
    collapsible = inp.get("collapsible", False)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_capacity"],
        "volume_liters": volume,
        "is_stackable": stackable,
        "is_collapsible": collapsible,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Finalizes the basket record and generates the output result."""
    certified = state.get("integrity_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": certified,
            "attributes": {
                "material": state.get("material"),
                "volume": f"{state.get('volume_liters')}L",
                "stackable": state.get("is_stackable"),
                "collapsible": state.get("is_collapsible"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specs", inspect_specs)
_g.add_node("evaluate_capacity", evaluate_capacity)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "evaluate_capacity")
_g.add_edge("evaluate_capacity", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
