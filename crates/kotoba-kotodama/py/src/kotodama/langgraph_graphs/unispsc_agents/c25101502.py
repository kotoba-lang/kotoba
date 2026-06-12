# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101502 — Bus Spec (segment 25).
Bespoke logic for bus specification validation and configuration.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101502"
UNISPSC_TITLE = "Bus Spec"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bus Spec
    seating_capacity: int
    powertrain_type: str
    emissions_tier: str
    safety_compliance: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input bus specifications for basic compliance."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity", 0)
    powertrain = inp.get("powertrain", "diesel")

    # Simple validation logic
    is_valid = capacity > 0 and capacity <= 100

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "seating_capacity": capacity,
        "powertrain_type": powertrain,
        "safety_compliance": is_valid,
    }


def configure_powertrain(state: State) -> dict[str, Any]:
    """Assigns emissions standards based on the powertrain type."""
    ptype = state.get("powertrain_type", "diesel")

    tier = "EURO_VI"
    if ptype.lower() in ["electric", "hydrogen"]:
        tier = "ZERO_EMISSION"
    elif ptype.lower() == "hybrid":
        tier = "ULTRA_LOW_EMISSION"

    return {
        "log": [f"{UNISPSC_CODE}:configure_powertrain"],
        "emissions_tier": tier,
    }


def finalize_bus_spec(state: State) -> dict[str, Any]:
    """Compiles the final bus specification document."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_bus_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "capacity": state.get("seating_capacity"),
                "powertrain": state.get("powertrain_type"),
                "emissions": state.get("emissions_tier"),
                "status": "APPROVED" if state.get("safety_compliance") else "REJECTED",
            },
            "ok": state.get("safety_compliance", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("powertrain", configure_powertrain)
_g.add_node("finalize", finalize_bus_spec)

_g.add_edge(START, "validate")
_g.add_edge("validate", "powertrain")
_g.add_edge("powertrain", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
