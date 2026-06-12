# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25170000 — Transportation components and systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25170000"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25170000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Transportation components and systems
    serial_number: str
    safety_rating: float
    is_certified: bool
    storage_location: str


def inspect_specs(state: State) -> dict[str, Any]:
    """Initial specification inspection of the transportation component."""
    inp = state.get("input") or {}
    sn = inp.get("sn", "SN-TEMP-001")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "serial_number": sn,
    }


def run_safety_validation(state: State) -> dict[str, Any]:
    """Execute safety validation protocols for the transportation system."""
    # Simulated safety check logic
    rating = 0.98
    return {
        "log": [f"{UNISPSC_CODE}:run_safety_validation"],
        "safety_rating": rating,
        "is_certified": rating >= 0.9,
    }


def finalize_asset_registration(state: State) -> dict[str, Any]:
    """Finalize the component registration in the inventory database."""
    certified = state.get("is_certified", False)
    location = "ZONE-ALPHA-5" if certified else "RE-INSPECTION-DOCK"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_registration"],
        "storage_location": location,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": certified,
            "metadata": {
                "serial_number": state.get("serial_number"),
                "safety_rating": state.get("safety_rating"),
                "assigned_location": location
            }
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specs)
_g.add_node("validate", run_safety_validation)
_g.add_node("register", finalize_asset_registration)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "validate")
_g.add_edge("validate", "register")
_g.add_edge("register", END)

graph = _g.compile()
