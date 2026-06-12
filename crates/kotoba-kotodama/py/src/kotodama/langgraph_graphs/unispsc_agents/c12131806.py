# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12131806 — Chemical (segment 12).

Bespoke graph logic for chemical substance processing, safety assessment,
and regulatory classification. This agent handles the lifecycle of chemical
data within the Etz Hayyim actor network.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12131806"
UNISPSC_TITLE = "Chemical"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12131806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical
    cas_number: str
    purity_level: float
    is_hazardous: bool
    safety_protocol: str
    storage_temp_c: float


def inspect_composition(state: State) -> dict[str, Any]:
    """Analyzes the chemical composition and purity from input data."""
    inp = state.get("input") or {}
    cas = inp.get("cas", "00-00-0")
    purity = float(inp.get("purity", 0.95))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "cas_number": cas,
        "purity_level": purity,
        "storage_temp_c": 20.0,
    }


def calculate_hazard_profile(state: State) -> dict[str, Any]:
    """Determines safety requirements based on CAS and purity."""
    cas = state.get("cas_number", "")
    purity = state.get("purity_level", 0.0)

    # Logic: High purity or specific CAS patterns trigger hazard flags
    hazardous = purity > 0.99 or cas.startswith("77")
    protocol = "Level 3 PPE" if hazardous else "Standard Lab Coat"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_hazard_profile"],
        "is_hazardous": hazardous,
        "safety_protocol": protocol,
    }


def generate_regulatory_report(state: State) -> dict[str, Any]:
    """Compiles the final result for the chemical substance."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_regulatory_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "cas": state.get("cas_number"),
            "compliance": {
                "hazardous": state.get("is_hazardous"),
                "protocol": state.get("safety_protocol"),
                "storage": f"{state.get('storage_temp_c')}C",
            },
            "did": UNISPSC_DID,
            "verified": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_composition", inspect_composition)
_g.add_node("calculate_hazard_profile", calculate_hazard_profile)
_g.add_node("generate_regulatory_report", generate_regulatory_report)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "calculate_hazard_profile")
_g.add_edge("calculate_hazard_profile", "generate_regulatory_report")
_g.add_edge("generate_regulatory_report", END)

graph = _g.compile()
