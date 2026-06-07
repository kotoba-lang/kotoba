# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24130000 — Refrigeration Spec (segment 24).

Bespoke logic for defining refrigeration system specifications, including
thermal requirement validation and component class assignment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24130000"
UNISPSC_TITLE = "Refrigeration Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24130000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    target_temp_c: float
    refrigerant_type: str
    thermal_load_kw: float
    efficiency_rating: str
    is_compliant: bool


def ingest_requirements(state: State) -> dict[str, Any]:
    """Parses raw input and initializes the refrigeration design state."""
    inp = state.get("input") or {}
    target_temp = float(inp.get("target_temp", -18.0))
    volume_m3 = float(inp.get("volume", 100.0))
    # Basic load estimation: 0.05 kW per m3 for standard insulated spaces
    calculated_load = volume_m3 * 0.05

    return {
        "log": [f"{UNISPSC_CODE}:ingest_requirements"],
        "target_temp_c": target_temp,
        "thermal_load_kw": calculated_load,
    }


def validate_thermal_limits(state: State) -> dict[str, Any]:
    """Checks if the requested temperature and load are within safe operational bounds."""
    temp = state.get("target_temp_c", 0.0)
    load = state.get("thermal_load_kw", 0.0)

    # Standard refrigeration typically operates between -50C and +15C
    compliant = (-50.0 <= temp <= 15.0) and (0.0 < load < 1000.0)

    return {
        "log": [f"{UNISPSC_CODE}:validate_thermal_limits"],
        "is_compliant": compliant,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Assigns component classes and compiles the final result."""
    temp = state.get("target_temp_c", 0.0)
    load = state.get("thermal_load_kw", 0.0)
    compliant = state.get("is_compliant", False)

    if not compliant:
        return {
            "log": [f"{UNISPSC_CODE}:finalize_failed"],
            "result": {
                "error": "Requirements exceed standard refrigeration parameters",
                "ok": False
            }
        }

    # Determine refrigerant and rating based on temperature range
    if temp < -30:
        ref = "R-404A"
        rating = "Low-Temp Specialist"
    elif temp < 0:
        ref = "R-134a"
        rating = "Medium-Temp Industrial"
    else:
        ref = "R-717 (Ammonia)"
        rating = "High-Efficiency Commercial"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "refrigerant_type": ref,
        "efficiency_rating": rating,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "spec": {
                "refrigerant": ref,
                "load_kw": round(load, 2),
                "rating": rating,
                "target_temp_c": temp
            },
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_requirements)
_g.add_node("validate", validate_thermal_limits)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "validate")
_g.add_edge("validate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
