# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162117 — Mineral (segment 11).

This agent handles the lifecycle of Mineral assets, providing domain-specific
logic for assaying raw ore, determining commercial grades, and generating
manifest metadata within the Etz Hayyim actor framework.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162117"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162117"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Minerals
    ore_density: float
    chemical_composition: str
    purity_grade: str
    is_hazardous: bool
    extraction_site_id: str


def analyze_assay(state: State) -> dict[str, Any]:
    """Analyzes the input assay data for mineral properties."""
    inp = state.get("input") or {}
    # Simulate extraction of data from the input payload
    density = float(inp.get("density", 2.65))
    composition = str(inp.get("composition", "Silicate-based"))
    site_id = str(inp.get("site_id", "LOC-000-UNKN"))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_assay"],
        "ore_density": density,
        "chemical_composition": composition,
        "extraction_site_id": site_id,
    }


def classify_commercial_grade(state: State) -> dict[str, Any]:
    """Determines the market grade based on mineral density and composition."""
    density = state.get("ore_density", 0.0)
    composition = state.get("chemical_composition", "")

    # Simple logic to determine grade
    if density > 4.5:
        grade = "High-Density Metallic"
    elif "Silicate" in composition:
        grade = "Industrial Non-Metallic"
    else:
        grade = "Standard Commercial"

    hazardous = any(token in composition for token in ["Arsenic", "Lead", "Mercury"])

    return {
        "log": [f"{UNISPSC_CODE}:classify_commercial_grade"],
        "purity_grade": grade,
        "is_hazardous": hazardous,
    }


def synthesize_mineral_manifest(state: State) -> dict[str, Any]:
    """Synthesizes the final result object for the mineral transaction."""
    return {
        "log": [f"{UNISPSC_CODE}:synthesize_mineral_manifest"],
        "result": {
            "unispsc_metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "segment": UNISPSC_SEGMENT,
                "did": UNISPSC_DID,
            },
            "asset_profile": {
                "grade": state.get("purity_grade"),
                "density": state.get("ore_density"),
                "composition": state.get("chemical_composition"),
                "site": state.get("extraction_site_id"),
                "safety_flags": ["HAZMAT"] if state.get("is_hazardous") else []
            },
            "processed": True
        }
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_assay)
_g.add_node("classify", classify_commercial_grade)
_g.add_node("manifest", synthesize_mineral_manifest)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "classify")
_g.add_edge("classify", "manifest")
_g.add_edge("manifest", END)

graph = _g.compile()
