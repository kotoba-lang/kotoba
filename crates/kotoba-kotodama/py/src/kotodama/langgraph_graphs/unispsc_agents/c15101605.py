# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15101605 — Lubricant (segment 15).

Bespoke graph logic for lubricant specification validation, purity analysis,
and quality assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15101605"
UNISPSC_TITLE = "Lubricant"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15101605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Lubricant
    viscosity_index: int
    oil_base_stock: str
    contamination_ppm: float
    flash_point_verified: bool


def validate_properties(state: State) -> dict[str, Any]:
    """Validates basic physical properties of the lubricant."""
    inp = state.get("input") or {}
    visc = inp.get("viscosity_index", 100)
    base = inp.get("base_stock", "mineral")

    return {
        "log": [f"{UNISPSC_CODE}:validate_properties"],
        "viscosity_index": visc,
        "oil_base_stock": base,
    }


def analyze_purity(state: State) -> dict[str, Any]:
    """Checks for contamination levels and flash point compliance."""
    inp = state.get("input") or {}
    ppm = inp.get("contamination_ppm", 0.0)
    flash = inp.get("flash_point_celsius", 200)

    # Standard compliance: clean if < 100ppm, flash point > 180C
    is_safe = ppm < 100.0 and flash > 180

    return {
        "log": [f"{UNISPSC_CODE}:analyze_purity"],
        "contamination_ppm": ppm,
        "flash_point_verified": is_safe,
    }


def finalize_assessment(state: State) -> dict[str, Any]:
    """Generates the final Lubricant quality assessment report."""
    safe = state.get("flash_point_verified", False)
    visc = state.get("viscosity_index", 0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_assessment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "viscosity": visc,
                "base": state.get("oil_base_stock"),
                "purity_pass": safe
            },
            "status": "QUALIFIED" if safe and visc > 0 else "QUARANTINE",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_properties)
_g.add_node("analyze", analyze_purity)
_g.add_node("emit", finalize_assessment)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
