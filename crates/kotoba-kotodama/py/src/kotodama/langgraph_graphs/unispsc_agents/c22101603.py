# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101603 — Bearing (segment 22).

Bespoke LangGraph agent for cataloging and validating mechanical bearings.
Handles dimensional verification, load capacity assessment, and cataloging.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101603"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bearing
    bore_diameter: float
    load_capacity: float
    lubrication_type: str
    is_compliant: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Inspects the input for bearing dimensions and lubrication requirements."""
    inp = state.get("input") or {}
    bore = inp.get("bore_diameter", 0.0)
    lubrication = inp.get("lubrication", "standard")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "bore_diameter": bore,
        "lubrication_type": lubrication,
    }


def verify_load_rating(state: State) -> dict[str, Any]:
    """Verifies the load capacity based on the bore diameter and material properties."""
    bore = state.get("bore_diameter", 0.0)
    # Simple calculation for a hypothetical dynamic load capacity
    capacity = bore * 12.75

    return {
        "log": [f"{UNISPSC_CODE}:verify_load_rating"],
        "load_capacity": capacity,
        "is_compliant": bore > 0,
    }


def catalog_bearing_entry(state: State) -> dict[str, Any]:
    """Finalizes the bearing entry in the technical catalog."""
    is_ok = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:catalog_bearing_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "bore_mm": state.get("bore_diameter"),
            "load_rating_kn": state.get("load_capacity"),
            "lubrication": state.get("lubrication_type"),
            "status": "CATALOGED" if is_ok else "REJECTED",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("verify_load_rating", verify_load_rating)
_g.add_node("catalog_bearing_entry", catalog_bearing_entry)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "verify_load_rating")
_g.add_edge("verify_load_rating", "catalog_bearing_entry")
_g.add_edge("catalog_bearing_entry", END)

graph = _g.compile()
