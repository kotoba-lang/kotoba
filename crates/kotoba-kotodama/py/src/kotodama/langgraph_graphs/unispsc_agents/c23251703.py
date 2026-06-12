# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251703 — Forging Spec (segment 23).

This bespoke implementation provides domain-specific logic for defining
forging specifications, including material analysis and thermal profiling.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251703"
UNISPSC_TITLE = "Forging Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251703"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Forging Spec
    alloy_grade: str
    target_temperature_celsius: int
    cooling_method: str
    tolerance_threshold: float


def analyze_material_requirements(state: State) -> dict[str, Any]:
    """Analyzes the requested alloy and determines initial forging parameters."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "AISI 4140")

    # Determine cooling method based on common metallurgy standards
    cooling = "Controlled Furnace Cool" if "4140" in alloy else "Air Cool"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_material_requirements"],
        "alloy_grade": alloy,
        "cooling_method": cooling,
    }


def calculate_thermal_profile(state: State) -> dict[str, Any]:
    """Calculates the optimal forging temperature for the identified alloy."""
    alloy = state.get("alloy_grade", "AISI 4140")

    # Heuristic temperature mapping
    temp = 1230 if "4140" in alloy else 1150
    tolerance = 0.05 if temp > 1200 else 0.10

    return {
        "log": [f"{UNISPSC_CODE}:calculate_thermal_profile"],
        "target_temperature_celsius": temp,
        "tolerance_threshold": tolerance,
    }


def finalize_forging_specification(state: State) -> dict[str, Any]:
    """Compiles the final specification result for the forging process."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_forging_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("alloy_grade"),
                "forging_temp": state.get("target_temperature_celsius"),
                "cooling": state.get("cooling_method"),
                "tolerance_mm": state.get("tolerance_threshold"),
            },
            "compliance_status": "APPROVED",
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_material_requirements)
_g.add_node("thermal", calculate_thermal_profile)
_g.add_node("finalize", finalize_forging_specification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "thermal")
_g.add_edge("thermal", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
