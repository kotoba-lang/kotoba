# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111062"
UNISPSC_TITLE = "Polymer"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111062"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for "Polymer"
    molecular_chain_type: str
    viscosity_rating: float
    thermal_stability_verified: bool
    batch_purity: float


def validate_polymer_spec(state: State) -> dict[str, Any]:
    """Validates the input specification for the polymer batch."""
    inp = state.get("input") or {}
    chain = inp.get("chain_type", "synthetic_linear")
    return {
        "log": [f"{UNISPSC_CODE}:validate_polymer_spec:{chain}"],
        "molecular_chain_type": chain,
    }


def process_viscosity_test(state: State) -> dict[str, Any]:
    """Simulates a viscosity test on the polymer structure."""
    chain = state.get("molecular_chain_type", "unknown")
    # Simulated calculation based on molecular structure
    visc = 240.5 if "linear" in chain else 180.0
    return {
        "log": [f"{UNISPSC_CODE}:process_viscosity_test:{visc}cP"],
        "viscosity_rating": visc,
        "thermal_stability_verified": True,
        "batch_purity": 0.9992,
    }


def emit_quality_certificate(state: State) -> dict[str, Any]:
    """Finalizes the process and emits a quality certificate for the polymer."""
    visc = state.get("viscosity_rating", 0.0)
    purity = state.get("batch_purity", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:emit_quality_certificate:pass"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "viscosity": visc,
                "purity": purity,
                "thermal_stable": state.get("thermal_stability_verified"),
            },
            "certified": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_polymer_spec)
_g.add_node("test", process_viscosity_test)
_g.add_node("emit", emit_quality_certificate)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
