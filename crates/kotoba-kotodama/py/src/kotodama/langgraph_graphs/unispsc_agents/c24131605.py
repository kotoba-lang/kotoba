# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131605 — Freezer Spec (segment 24).

Bespoke graph logic for industrial and commercial freezer specification validation,
energy efficiency analysis, and thermal requirement verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131605"
UNISPSC_TITLE = "Freezer Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Freezer Specification
    target_temperature_c: float
    storage_volume_liters: int
    insulation_type: str
    energy_star_compliant: bool
    validation_score: float


def validate_requirements(state: State) -> dict[str, Any]:
    """Checks the baseline specifications against industrial standards."""
    inp = state.get("input") or {}
    temp = float(inp.get("temp_c", -18.0))
    volume = int(inp.get("volume_l", 200))

    # Freezers must maintain sub-zero temperatures
    is_valid = temp <= 0 and volume > 0
    score = 100.0 if is_valid else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "target_temperature_c": temp,
        "storage_volume_liters": volume,
        "validation_score": score,
    }


def compute_efficiency(state: State) -> dict[str, Any]:
    """Calculates simulated energy efficiency based on thermal parameters."""
    temp = state.get("target_temperature_c", -18.0)
    volume = state.get("storage_volume_liters", 200)

    # Dummy logic: Ultra-low freezers need better insulation
    if temp < -40.0:
        insulation = "Vacuum Insulated Panel"
        compliant = volume < 500  # Large ultra-low units have higher consumption
    else:
        insulation = "Polyurethane Foam"
        compliant = True

    return {
        "log": [f"{UNISPSC_CODE}:compute_efficiency"],
        "insulation_type": insulation,
        "energy_star_compliant": compliant,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Produces the final verified specification document."""
    score = state.get("validation_score", 0.0)
    compliant = state.get("energy_star_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "CERTIFIED" if (score > 80 and compliant) else "PENDING",
            "insulation": state.get("insulation_type"),
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("analyze", compute_efficiency)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
