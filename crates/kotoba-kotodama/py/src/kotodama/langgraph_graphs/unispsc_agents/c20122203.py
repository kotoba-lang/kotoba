# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122203 — Robot Gear (segment 20).

Bespoke graph logic for mechanical robot transmission components, including
precision gearing, torque analysis, and material specification workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122203"
UNISPSC_TITLE = "Robot Gear"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122203"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Robot Gear
    gear_ratio: float
    material_grade: str
    backlash_arcmin: float
    is_harmonic_drive: bool
    lubrication_standard: str


def validate_mechanical_intent(state: State) -> dict[str, Any]:
    """Validates the gear specifications and determines the drive architecture."""
    inp = state.get("input") or {}
    ratio = float(inp.get("ratio", 50.0))
    is_harmonic = ratio >= 30.0  # Simple heuristic for high-reduction gears

    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanical_intent"],
        "gear_ratio": ratio,
        "is_harmonic_drive": is_harmonic,
        "material_grade": inp.get("material", "Hardened Steel"),
    }


def compute_tolerances(state: State) -> dict[str, Any]:
    """Calculates precision metrics based on gear type and ratio."""
    is_harmonic = state.get("is_harmonic_drive", False)
    # Harmonic drives typically have zero-backlash characteristics
    backlash = 0.1 if is_harmonic else 3.0
    lubricant = "Synthetic Grease (High-Temp)" if is_harmonic else "Standard Gear Oil"

    return {
        "log": [f"{UNISPSC_CODE}:compute_tolerances"],
        "backlash_arcmin": backlash,
        "lubrication_standard": lubricant,
    }


def finalize_gear_manifest(state: State) -> dict[str, Any]:
    """Assembles the final engineering manifest for the robot gear component."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_gear_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "ratio": state.get("gear_ratio"),
                "material": state.get("material_grade"),
                "backlash_limit": state.get("backlash_arcmin"),
                "lubricant": state.get("lubrication_standard"),
                "drive_type": "Harmonic" if state.get("is_harmonic_drive") else "Spur/Helical",
            },
            "compliance": "ISO-9001-MECH",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_mechanical_intent)
_g.add_node("analyze", compute_tolerances)
_g.add_node("emit", finalize_gear_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
