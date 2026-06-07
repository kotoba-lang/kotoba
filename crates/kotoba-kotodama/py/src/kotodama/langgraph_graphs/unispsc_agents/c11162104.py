# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162104 — Catalyst (segment 11).

Bespoke graph logic for catalytic reaction simulation, focusing on
activation energy reduction and reaction efficiency modeling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162104"
UNISPSC_TITLE = "Catalyst"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Catalyst
    catalyst_purity: float
    activation_energy_delta: float
    reaction_stability: str
    is_spent: bool


def inspect_catalyst(state: State) -> dict[str, Any]:
    """Evaluates the input catalyst properties and purity level."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.98)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_catalyst - Purity at {purity:.2%}"],
        "catalyst_purity": purity,
        "is_spent": False
    }


def calculate_kinetics(state: State) -> dict[str, Any]:
    """Simulates the kinetic shift caused by the catalyst interaction."""
    purity = state.get("catalyst_purity", 0.0)
    # Simple model: higher purity leads to greater activation energy reduction
    energy_reduction = purity * 15.5  # kcal/mol
    stability = "high" if purity > 0.95 else "moderate"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_kinetics - Delta Ea: -{energy_reduction:.2f} kcal/mol"],
        "activation_energy_delta": energy_reduction,
        "reaction_stability": stability
    }


def validate_yield(state: State) -> dict[str, Any]:
    """Validates the predicted reaction yield and finalizes the state."""
    stability = state.get("reaction_stability", "unknown")
    delta_ea = state.get("activation_energy_delta", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_yield - Stability: {stability}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "energy_reduction": delta_ea,
                "stability": stability
            },
            "status": "ready" if stability == "high" else "caution",
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("inspect_catalyst", inspect_catalyst)
_g.add_node("calculate_kinetics", calculate_kinetics)
_g.add_node("validate_yield", validate_yield)

_g.add_edge(START, "inspect_catalyst")
_g.add_edge("inspect_catalyst", "calculate_kinetics")
_g.add_edge("calculate_kinetics", "validate_yield")
_g.add_edge("validate_yield", END)

graph = _g.compile()
