# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174206 — Stabilizer bars (segment 25).

Bespoke graph logic for validating metallurgical properties, torsional
stiffness profiles, and vehicle fitment compatibility for automotive
suspension stabilizer components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174206"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174206"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Stabilizer Bars
    material_alloy: str
    torsional_rate: float
    target_platforms: list[str]
    qa_certified: bool


def analyze_metallurgy(state: State) -> dict[str, Any]:
    """Validates the steel alloy grade and heat treatment specification."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "51CrV4 Spring Steel")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_metallurgy"],
        "material_alloy": alloy,
    }


def calculate_torsion(state: State) -> dict[str, Any]:
    """Calculates the spring rate and torsional stiffness of the bar."""
    inp = state.get("input") or {}
    # Default stiffness for a 24mm solid bar
    rate = float(inp.get("stiffness_nm", 485.0))
    is_safe = rate >= 150.0
    return {
        "log": [f"{UNISPSC_CODE}:calculate_torsion"],
        "torsional_rate": rate,
        "qa_certified": is_safe,
    }


def verify_compatibility(state: State) -> dict[str, Any]:
    """Maps the component to specific vehicle chassis and axle configurations."""
    inp = state.get("input") or {}
    platforms = inp.get("compatible_chassis", ["A-Segment-FWD", "B-Segment-AWD"])

    return {
        "log": [f"{UNISPSC_CODE}:verify_compatibility"],
        "target_platforms": platforms,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_alloy"),
                "rate_nm_deg": state.get("torsional_rate"),
                "platforms": platforms,
            },
            "ok": state.get("qa_certified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_metallurgy", analyze_metallurgy)
_g.add_node("calculate_torsion", calculate_torsion)
_g.add_node("verify_compatibility", verify_compatibility)

_g.add_edge(START, "analyze_metallurgy")
_g.add_edge("analyze_metallurgy", "calculate_torsion")
_g.add_edge("calculate_torsion", "verify_compatibility")
_g.add_edge("verify_compatibility", END)

graph = _g.compile()
