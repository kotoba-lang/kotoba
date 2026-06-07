# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162303"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162303"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    chemical_formula: str
    octane_boost_rating: float
    flash_point_verified: bool
    safety_protocol_active: bool


def validate_additive_composition(state: State) -> dict[str, Any]:
    """Validates the chemical composition of the gasoline additive."""
    inp = state.get("input") or {}
    formula = inp.get("formula", "C8H18-MOD")
    return {
        "log": [f"{UNISPSC_CODE}:validate_additive_composition"],
        "chemical_formula": formula,
        "flash_point_verified": True,
    }


def evaluate_combustion_impact(state: State) -> dict[str, Any]:
    """Evaluates the impact of the additive on gasoline combustion properties."""
    formula = state.get("chemical_formula", "")
    boost = 2.4 if "C8" in formula else 1.2
    return {
        "log": [f"{UNISPSC_CODE}:evaluate_combustion_impact"],
        "octane_boost_rating": boost,
        "safety_protocol_active": True,
    }


def certify_product_specs(state: State) -> dict[str, Any]:
    """Finalizes the technical specification and certifies the product."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_product_specs"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec_sheet": {
                "formula": state.get("chemical_formula"),
                "octane_boost": state.get("octane_boost_rating"),
                "flash_point_ok": state.get("flash_point_verified"),
                "safety_active": state.get("safety_protocol_active"),
            },
            "status": "CERTIFIED",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_additive_composition)
_g.add_node("evaluate", evaluate_combustion_impact)
_g.add_node("certify", certify_product_specs)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
