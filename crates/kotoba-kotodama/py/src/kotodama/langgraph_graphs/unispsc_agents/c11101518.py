# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101518 — Hydrocarbon (segment 11).

Bespoke graph logic for managing hydrocarbon chemical specifications,
purity analysis, and certification of batch quality.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101518"
UNISPSC_TITLE = "Hydrocarbon"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101518"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_grade: float
    cas_registry_number: str
    density_measured: float
    viscosity_cp: float
    is_volatile: bool


def verify_composition(state: State) -> dict[str, Any]:
    """Identifies the chemical identity and basic physical properties."""
    inp = state.get("input") or {}
    cas = inp.get("cas", "N/A")
    volatility = inp.get("volatility", True)
    return {
        "log": [f"{UNISPSC_CODE}:verify_composition"],
        "cas_registry_number": cas,
        "is_volatile": volatility,
    }


def analyze_purity(state: State) -> dict[str, Any]:
    """Evaluates purity levels and measures critical density/viscosity."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.992))
    density = float(inp.get("density", 0.75))
    viscosity = float(inp.get("viscosity", 1.2))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_purity"],
        "purity_grade": purity,
        "density_measured": density,
        "viscosity_cp": viscosity,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Finalizes the certification based on purity thresholds."""
    purity = state.get("purity_grade", 0.0)
    is_certified = purity >= 0.995

    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "cas": state.get("cas_registry_number"),
            "certified": is_certified,
            "purity": purity,
            "properties": {
                "density": state.get("density_measured"),
                "viscosity": state.get("viscosity_cp")
            },
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_composition", verify_composition)
_g.add_node("analyze_purity", analyze_purity)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "verify_composition")
_g.add_edge("verify_composition", "analyze_purity")
_g.add_edge("analyze_purity", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
