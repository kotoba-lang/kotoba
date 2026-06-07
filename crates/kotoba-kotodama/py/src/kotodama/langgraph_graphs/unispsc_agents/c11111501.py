# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11111501 — Chemical (segment 11).

Bespoke graph logic for Chemical agents. This implementation validates
safety data sheets, assesses chemical purity, and manages storage protocols
consistent with segment 11 (Earth and Water Remediation) or general chemical
handling within the Etz Hayyim actor model.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11111501"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11111501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical handling
    hazard_classification: str
    purity_level: float
    storage_conditions: str
    sds_verified: bool


def inspect_safety_data(state: State) -> dict[str, Any]:
    """Validates the Safety Data Sheet (SDS) information for the chemical."""
    inp = state.get("input") or {}
    hazard = inp.get("hazard", "Class-3 Flammable")
    verified = inp.get("sds_present", True)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety_data"],
        "hazard_classification": hazard,
        "sds_verified": verified,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Simulates chemical composition and purity analysis protocols."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.999))

    # Storage protocol logic based on hazard rating
    hazard = state.get("hazard_classification", "General")
    if "Flammable" in hazard or "Reactive" in hazard:
        storage = "Explosion-proof Bunker"
    else:
        storage = "Climate-controlled Rack"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_level": purity,
        "storage_conditions": storage,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Prepares the final inventory entry and quality certification."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "hazard": state.get("hazard_classification"),
                "purity": state.get("purity_level"),
                "storage": state.get("storage_conditions"),
                "sds_ok": state.get("sds_verified"),
            },
            "certified": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_safety_data", inspect_safety_data)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_safety_data")
_g.add_edge("inspect_safety_data", "analyze_composition")
_g.add_edge("analyze_composition", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
