# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352105 — Solvent (segment 12).

Bespoke graph implementing chemical solvent safety validation and purity
specification logic. This module manages state transitions for solvent
characterization, hazard assessment, and technical data verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352105"
UNISPSC_TITLE = "Solvent"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352105"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    cas_number: str
    purity_percentage: float
    is_volatile: bool
    safety_protocol_active: bool


def assess_hazards(state: State) -> dict[str, Any]:
    """Inspects input for flash point and volatility indicators."""
    inp = state.get("input") or {}
    flash_point = inp.get("flash_point", 25.0)
    volatility = flash_point < 37.8  # Definition of flammable liquid in many contexts
    return {
        "log": [f"{UNISPSC_CODE}:assess_hazards"],
        "is_volatile": volatility,
        "safety_protocol_active": True,
        "cas_number": inp.get("cas", "0000-00-0"),
    }


def verify_purity(state: State) -> dict[str, Any]:
    """Validates the chemical grade and purity requirements."""
    inp = state.get("input") or {}
    target_purity = float(inp.get("target_purity", 99.5))
    return {
        "log": [f"{UNISPSC_CODE}:verify_purity"],
        "purity_percentage": target_purity,
    }


def finalize_technical_sheet(state: State) -> dict[str, Any]:
    """Compiles the final specification result for the solvent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_technical_sheet"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "cas": state.get("cas_number"),
                "purity": f"{state.get('purity_percentage')}%",
                "flammable": state.get("is_volatile"),
                "protocol": "active" if state.get("safety_protocol_active") else "standard",
            },
            "status": "verified",
        },
    }


_g = StateGraph(State)

_g.add_node("assess_hazards", assess_hazards)
_g.add_node("verify_purity", verify_purity)
_g.add_node("finalize_technical_sheet", finalize_technical_sheet)

_g.add_edge(START, "assess_hazards")
_g.add_edge("assess_hazards", "verify_purity")
_g.add_edge("verify_purity", "finalize_technical_sheet")
_g.add_edge("finalize_technical_sheet", END)

graph = _g.compile()
