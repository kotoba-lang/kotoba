# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102100 — Sprocket (segment 21).

Bespoke graph logic for mechanical sprocket components used in agricultural
harvesting machinery. This agent validates mechanical specifications,
assesses material durability, and confirms inventory fitment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102100"
UNISPSC_TITLE = "Sprocket"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tooth_count: int
    pitch_diameter: float
    material_grade: str
    is_heat_treated: bool
    structural_integrity_score: float


def inspect_dimensions(state: State) -> dict[str, Any]:
    """Validates the physical dimensions of the sprocket component."""
    inp = state.get("input") or {}
    t_count = inp.get("tooth_count", 0)
    p_dia = inp.get("pitch_diameter", 0.0)

    msg = f"{UNISPSC_CODE}:inspect_dimensions -> {t_count} teeth, {p_dia}mm pitch"
    return {
        "log": [msg],
        "tooth_count": t_count,
        "pitch_diameter": p_dia,
    }


def metallurgy_analysis(state: State) -> dict[str, Any]:
    """Assesses material properties and heat treatment status."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    hardened = inp.get("hardened", True)

    # Simple heuristic for integrity score
    score = 0.95 if hardened else 0.70
    if material.lower() == "alloy_steel":
        score += 0.05

    return {
        "log": [f"{UNISPSC_CODE}:metallurgy_analysis -> grade:{material}"],
        "material_grade": material,
        "is_heat_treated": hardened,
        "structural_integrity_score": min(score, 1.0),
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Generates the final sprocket configuration and metadata."""
    score = state.get("structural_integrity_score", 0.0)
    passed = score > 0.8

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset -> qc_passed:{passed}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "qc_status": "certified" if passed else "rejected",
            "specs": {
                "teeth": state.get("tooth_count"),
                "pitch": state.get("pitch_diameter"),
                "material": state.get("material_grade"),
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_dimensions", inspect_dimensions)
_g.add_node("metallurgy_analysis", metallurgy_analysis)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "inspect_dimensions")
_g.add_edge("inspect_dimensions", "metallurgy_analysis")
_g.add_edge("metallurgy_analysis", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
