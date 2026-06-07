# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271802 — Flux (segment 23).
"""

from __future__ import annotations

import operator
# Ensure operator is available for the reducer
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271802"
UNISPSC_TITLE = "Flux"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    composition: str
    activity_level: str
    viscosity_pa_s: float
    safety_compliance: bool


def analyze_flux_properties(state: State) -> dict[str, Any]:
    """Analyzes the input for chemical and physical properties of the flux."""
    inp = state.get("input") or {}
    composition = inp.get("composition", "rosin-based")
    activity = inp.get("activity", "low")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_flux_properties"],
        "composition": composition,
        "activity_level": activity,
    }


def verify_safety_standards(state: State) -> dict[str, Any]:
    """Ensures the flux composition meets industrial safety standards."""
    comp = state.get("composition", "")
    # Lead-free flux is a common safety/environmental standard
    is_safe = "lead" not in comp.lower()
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_standards"],
        "safety_compliance": is_safe,
        "viscosity_pa_s": 0.5 if is_safe else 0.8,
    }


def finalize_technical_data_sheet(state: State) -> dict[str, Any]:
    """Generates the final specification for the flux product."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_technical_data_sheet"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "composition": state.get("composition"),
            "activity": state.get("activity_level"),
            "viscosity": state.get("viscosity_pa_s"),
            "safe": state.get("safety_compliance"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_flux_properties)
_g.add_node("verify", verify_safety_standards)
_g.add_node("finalize", finalize_technical_data_sheet)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
