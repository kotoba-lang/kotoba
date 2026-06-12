# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25102000"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25102000"


class State(TypedDict, total=False):
    """
    State for the Vehicle actor, tracking mechanical specs and compliance.
    """
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vin_verified: bool
    safety_rating: float
    emissions_tier: str
    powertrain_status: str


def inspect_chassis(state: State) -> dict[str, Any]:
    """Validates the vehicle identity and basic structure."""
    inp = state.get("input") or {}
    vin = inp.get("vin")
    is_valid = bool(vin and len(str(vin)) >= 11)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_chassis"],
        "vin_verified": is_valid,
        "powertrain_status": "initialized"
    }


def verify_standards(state: State) -> dict[str, Any]:
    """Calculates safety and emission classifications based on input data."""
    inp = state.get("input") or {}
    tier = inp.get("tier", "Euro 6")
    # Simulate a safety rating calculation
    rating = 4.5 if state.get("vin_verified") else 0.0
    return {
        "log": [f"{UNISPSC_CODE}:verify_standards"],
        "safety_rating": rating,
        "emissions_tier": tier
    }


def register_vehicle(state: State) -> dict[str, Any]:
    """Finalizes the vehicle record in the domain state."""
    success = state.get("vin_verified", False) and state.get("safety_rating", 0) > 0
    return {
        "log": [f"{UNISPSC_CODE}:register_vehicle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "registered" if success else "rejected",
            "safety": state.get("safety_rating"),
            "emissions": state.get("emissions_tier"),
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_chassis)
_g.add_node("verify", verify_standards)
_g.add_node("register", register_vehicle)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "register")
_g.add_edge("register", END)

graph = _g.compile()
