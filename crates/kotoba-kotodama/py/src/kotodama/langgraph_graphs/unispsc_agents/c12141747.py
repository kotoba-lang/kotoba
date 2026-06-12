# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141747 — Chemical (segment 12).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141747"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141747"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for "Chemical"
    cas_registry_number: str
    safety_data_sheet_verified: bool
    purity_level: float
    hazard_class: str


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the chemical identity and safety documentation."""
    inp = state.get("input") or {}
    cas = inp.get("cas_number", "00-00-0")
    has_sds = "sds_uri" in inp or "sds_data" in inp
    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "cas_registry_number": cas,
        "safety_data_sheet_verified": has_sds,
    }


def analyze_composition(state: State) -> dict[str, Any]:
    """Analyzes the chemical purity and determines hazard classification."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.995))

    # Simple logic to determine hazard class based on purity/input
    if purity < 0.90:
        h_class = "Industrial Grade"
    elif inp.get("flammable", False):
        h_class = "Flammable Liquid"
    else:
        h_class = "Standard Reagent"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_composition"],
        "purity_level": purity,
        "hazard_class": h_class,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Issues the final certification result for the chemical lot."""
    sds_ok = state.get("safety_data_sheet_verified", False)
    purity = state.get("purity_level", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "cas": state.get("cas_registry_number"),
            "purity": f"{purity:.2%}",
            "hazard_class": state.get("hazard_class"),
            "compliance_certified": sds_ok and purity > 0.95,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specification", validate_specification)
_g.add_node("analyze_composition", analyze_composition)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "analyze_composition")
_g.add_edge("analyze_composition", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
