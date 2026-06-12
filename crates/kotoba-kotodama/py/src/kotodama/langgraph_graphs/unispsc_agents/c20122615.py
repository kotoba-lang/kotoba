# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122615 — Bearing (segment 20).

Bespoke graph logic for mechanical bearing lifecycle management,
including specification validation, load dynamics analysis, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122615"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122615"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Bearing
    inner_diameter: float
    outer_diameter: float
    material_grade: str
    lubrication_required: bool
    dynamic_load_capacity: float


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material grade for the bearing."""
    inp = state.get("input") or {}
    id_val = float(inp.get("inner_diameter", 0.0))
    od_val = float(inp.get("outer_diameter", 0.0))
    grade = str(inp.get("material_grade", "Standard Steel"))

    # Bearing must have an outer diameter larger than the inner diameter
    is_valid = od_val > id_val > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications(id={id_val}, od={od_val}, valid={is_valid})"],
        "inner_diameter": id_val,
        "outer_diameter": od_val,
        "material_grade": grade,
        "lubrication_required": inp.get("require_lubrication", True)
    }


def analyze_load_dynamics(state: State) -> dict[str, Any]:
    """Calculates theoretical dynamic load capacity based on dimensions."""
    id_val = state.get("inner_diameter", 0.0)
    od_val = state.get("outer_diameter", 0.0)

    # Heuristic: Capacity proportional to cross-section area delta for this actor
    # A simplified model for internal state transition testing
    capacity = (od_val**2 - id_val**2) * 0.785 * 10
    if state.get("material_grade") == "Premium Ceramic":
        capacity *= 1.4

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_dynamics(capacity={capacity:.2f})"],
        "dynamic_load_capacity": capacity
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final compliance result for the bearing actor."""
    capacity = state.get("dynamic_load_capacity", 0.0)
    grade = state.get("material_grade", "Unknown")
    is_ok = capacity > 0 and state.get("outer_diameter", 0.0) > state.get("inner_diameter", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification(status={'OK' if is_ok else 'FAIL'})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "Verified" if is_ok else "Failed",
            "material": grade,
            "load_limit": capacity,
            "lubrication": "Required" if state.get("lubrication_required") else "Sealed",
            "ok": is_ok
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("analyze", analyze_load_dynamics)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
