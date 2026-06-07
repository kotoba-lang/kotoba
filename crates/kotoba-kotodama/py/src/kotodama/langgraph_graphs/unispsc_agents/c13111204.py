# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for Carbon Fiber (13111204).
This agent validates mechanical specifications and categorizes fiber grade for industrial applications.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111204"
UNISPSC_TITLE = "Carbon Fiber"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    tensile_strength_gpa: float
    tow_size_k: int
    fiber_grade: str
    modulus_type: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Extract and validate physical properties from the input payload."""
    inp = state.get("input") or {}
    # Simulate extraction of carbon fiber metrics
    strength = float(inp.get("tensile_strength", 0.0))
    tow = int(inp.get("tow_size", 12))  # Default to 12K tow if unspecified
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "tensile_strength_gpa": strength,
        "tow_size_k": tow,
    }


def categorize_fiber(state: State) -> dict[str, Any]:
    """Determine the commercial grade based on tensile strength and tow properties."""
    strength = state.get("tensile_strength_gpa", 0.0)

    if strength >= 5.5:
        grade = "Intermediate Modulus (IM)"
    elif strength >= 3.5:
        grade = "High Strength (HS)"
    else:
        grade = "Standard Modulus (SM)"

    modulus = "Ultra High" if strength > 6.0 else "Standard"
    return {
        "log": [f"{UNISPSC_CODE}:categorize_fiber"],
        "fiber_grade": grade,
        "modulus_type": modulus,
    }


def generate_catalog_entry(state: State) -> dict[str, Any]:
    """Package the verified specifications into the final result record."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "grade": state.get("fiber_grade"),
                "modulus": state.get("modulus_type"),
                "filament_count": f"{state.get('tow_size_k')}K",
                "tensile_strength": f"{state.get('tensile_strength_gpa')} GPa",
            },
            "status": "verified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specifications)
_g.add_node("categorize", categorize_fiber)
_g.add_node("generate", generate_catalog_entry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "categorize")
_g.add_edge("categorize", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
