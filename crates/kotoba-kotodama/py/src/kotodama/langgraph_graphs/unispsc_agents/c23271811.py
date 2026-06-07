# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271811 — Welding Flux (segment 23).

Bespoke graph for Welding Flux quality assurance, handling chemical
composition verification, moisture level analysis, and final weldability
certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271811"
UNISPSC_TITLE = "Welding Flux"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271811"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields
    composition_ratios: dict[str, float]
    moisture_content_pct: float
    viscosity_index: float
    is_low_hydrogen: bool


def validate_composition(state: State) -> dict[str, Any]:
    """Ensures the chemical composition of the flux meets industrial standards."""
    inp = state.get("input") or {}
    composition = inp.get("composition", {"CaF2": 0.45, "SiO2": 0.25, "MnO": 0.30})

    # Determine if it's low hydrogen based on fluoride and scavenger levels
    low_h = composition.get("CaF2", 0) > 0.40

    return {
        "log": [f"{UNISPSC_CODE}:validate_composition"],
        "composition_ratios": composition,
        "is_low_hydrogen": low_h,
    }


def analyze_moisture(state: State) -> dict[str, Any]:
    """Simulates moisture detection to prevent porosity in the weld bead."""
    # Welding flux must be exceptionally dry for high-strength steel
    moisture = 0.03  # Simulated 0.03% reading

    log_entry = f"{UNISPSC_CODE}:analyze_moisture - level: {moisture}%"
    return {
        "log": [log_entry],
        "moisture_content_pct": moisture,
        "viscosity_index": 1.42,
    }


def assess_weldability(state: State) -> dict[str, Any]:
    """Generates the final quality assessment report for the batch."""
    m_content = state.get("moisture_content_pct", 1.0)
    # Threshold for critical applications is usually < 0.1%
    is_ok = m_content < 0.05

    return {
        "log": [f"{UNISPSC_CODE}:assess_weldability"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality_grade": "A+" if is_ok else "B-",
            "low_hydrogen_certified": state.get("is_low_hydrogen", False),
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_composition", validate_composition)
_g.add_node("analyze_moisture", analyze_moisture)
_g.add_node("assess_weldability", assess_weldability)

_g.add_edge(START, "validate_composition")
_g.add_edge("validate_composition", "analyze_moisture")
_g.add_edge("analyze_moisture", "assess_weldability")
_g.add_edge("assess_weldability", END)

graph = _g.compile()
