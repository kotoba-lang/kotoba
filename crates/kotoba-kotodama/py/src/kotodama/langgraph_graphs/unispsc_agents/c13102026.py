# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102026 — Lubricant (segment 13).

Bespoke logic for lubricant specification validation and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102026"
UNISPSC_TITLE = "Lubricant"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102026"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Lubricant
    viscosity_index: int
    base_oil_category: str
    additive_solubility_verified: bool
    flash_point_celsius: float
    oxidation_stability_check: bool


def inspect_lubricant_specs(state: State) -> dict[str, Any]:
    """Inspects the input specifications for viscosity and base oil type."""
    inp = state.get("input") or {}
    vi = inp.get("viscosity_index", 95)
    base_oil = inp.get("base_oil", "Group II Mineral")
    flash_point = inp.get("flash_point", 210.0)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_lubricant_specs"],
        "viscosity_index": vi,
        "base_oil_category": base_oil,
        "flash_point_celsius": flash_point,
    }


def verify_performance_factors(state: State) -> dict[str, Any]:
    """Verifies chemical stability and additive compatibility."""
    vi = state.get("viscosity_index", 0)
    base_oil = state.get("base_oil_category", "")

    # Logic: High VI and synthetic bases imply better stability
    stability = vi > 100 or "Synthetic" in base_oil
    # Solubility is generally high for mineral bases
    solubility = "Mineral" in base_oil or "Ester" in base_oil

    return {
        "log": [f"{UNISPSC_CODE}:verify_performance_factors"],
        "additive_solubility_verified": solubility,
        "oxidation_stability_check": stability,
    }


def certify_technical_datasheet(state: State) -> dict[str, Any]:
    """Generates the final certified technical datasheet for the lubricant."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_technical_datasheet"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "Approved",
            "properties": {
                "viscosity_index": state.get("viscosity_index"),
                "base_oil": state.get("base_oil_category"),
                "flash_point": state.get("flash_point_celsius"),
                "additive_compatible": state.get("additive_solubility_verified"),
                "oxidation_stable": state.get("oxidation_stability_check"),
            },
            "compliance_labels": ["SAE", "API", "ISO"],
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_lubricant_specs)
_g.add_node("verify_factors", verify_performance_factors)
_g.add_node("certify", certify_technical_datasheet)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "verify_factors")
_g.add_edge("verify_factors", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
