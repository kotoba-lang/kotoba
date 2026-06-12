# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172903 — Rail Light (segment 25).

Bespoke logic for Rail Light components in commercial/military transport,
handling technical specification inspection and safety validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172903"
UNISPSC_TITLE = "Rail Light"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172903"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Rail Light
    voltage_rating: str
    lumen_output: int
    mounting_configuration: str
    safety_certification: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Inspects the technical specifications of the rail light component."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", "24V DC")
    lumens = inp.get("lumens", 1200)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "voltage_rating": voltage,
        "lumen_output": lumens,
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Validates the lighting unit against transit safety standards."""
    inp = state.get("input") or {}
    mount = inp.get("mounting", "Recessed")
    # Simulation of safety check based on voltage standards
    is_certified = state.get("voltage_rating") in ["12V DC", "24V DC", "110V AC"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "mounting_configuration": mount,
        "safety_certification": is_certified,
    }


def finalize_listing(state: State) -> dict[str, Any]:
    """Finalizes the component data for the UNISPSC registry."""
    is_ok = state.get("safety_certification", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_listing"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_ok,
            "specs": {
                "voltage": state.get("voltage_rating"),
                "lumens": state.get("lumen_output"),
                "mount": state.get("mounting_configuration")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("validate_safety", validate_safety)
_g.add_node("finalize_listing", finalize_listing)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "validate_safety")
_g.add_edge("validate_safety", "finalize_listing")
_g.add_edge("finalize_listing", END)

graph = _g.compile()
