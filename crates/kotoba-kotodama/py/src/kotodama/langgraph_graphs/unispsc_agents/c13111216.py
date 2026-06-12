# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for Carbon Fiber (UNISPSC 13111216).
This agent handles specifications and performance analysis for high-strength carbon fiber materials.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111216"
UNISPSC_TITLE = "Carbon Fiber"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111216"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Carbon Fiber
    tow_count: int  # e.g., 3000 (3k), 12000 (12k)
    tensile_strength_mpa: float
    tensile_modulus_gpa: float
    fiber_type: str  # PAN-based, Pitch-based
    is_aerospace_grade: bool


def ingest_specifications(state: State) -> dict[str, Any]:
    """Validates and ingests raw carbon fiber technical specifications."""
    inp = state.get("input") or {}
    tow = inp.get("tow_count", 12000)
    strength = float(inp.get("tensile_strength", 4900.0))
    modulus = float(inp.get("tensile_modulus", 240.0))

    # Determine type and grade based on modulus and strength
    f_type = inp.get("fiber_type", "PAN-based")
    is_aero = strength > 4000 and modulus > 230

    return {
        "log": [f"{UNISPSC_CODE}:ingest_specifications[tow={tow}]"],
        "tow_count": tow,
        "tensile_strength_mpa": strength,
        "tensile_modulus_gpa": modulus,
        "fiber_type": f_type,
        "is_aerospace_grade": is_aero
    }


def calculate_performance_metrics(state: State) -> dict[str, Any]:
    """Calculates specific strength and modulus ratios for material application."""
    strength = state.get("tensile_strength_mpa", 0.0)
    modulus = state.get("tensile_modulus_gpa", 0.0)

    # Specific performance index
    perf_index = (strength / modulus) if modulus > 0 else 0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_performance_metrics[index={perf_index:.2f}]"],
        "result": {
            "performance_index": round(perf_index, 4),
            "recommendation": "Structural" if strength > 3500 else "General Purpose"
        }
    }


def finalize_material_data(state: State) -> dict[str, Any]:
    """Finalizes the carbon fiber agent result with a complete material manifest."""
    metrics = state.get("result") or {}

    manifest = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "properties": {
            "tow": state.get("tow_count"),
            "strength_mpa": state.get("tensile_strength_mpa"),
            "modulus_gpa": state.get("tensile_modulus_gpa"),
            "type": state.get("fiber_type"),
            "aerospace_qualified": state.get("is_aerospace_grade")
        },
        "analysis": metrics,
        "status": "verified"
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_data"],
        "result": manifest
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specifications)
_g.add_node("analyze", calculate_performance_metrics)
_g.add_node("finalize", finalize_material_data)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
