# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23201002 — Column (segment 23).
Bespoke logic for industrial column specification and structural validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201002"
UNISPSC_TITLE = "Column"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for industrial columns
    material: str
    pressure_rating_psi: float
    height_meters: float
    load_capacity_kn: float
    is_valid_spec: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the basic engineering requirements for the column."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "unknown"))
    height = float(inp.get("height_meters", 0.0))
    pressure = float(inp.get("pressure_rating_psi", 0.0))

    # Basic validation: columns must have height and a specified material
    is_valid = height > 0 and material.lower() != "unknown"

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material": material,
        "height_meters": height,
        "pressure_rating_psi": pressure,
        "is_valid_spec": is_valid
    }


def calculate_load_capacity(state: State) -> dict[str, Any]:
    """Calculates the theoretical load capacity based on material properties."""
    material_factors = {
        "steel": 250.0,
        "aluminum": 120.0,
        "concrete": 300.0,
        "reinforced_polymer": 180.0
    }

    mat = state.get("material", "unknown").lower()
    factor = material_factors.get(mat, 50.0)
    height = state.get("height_meters", 1.0)

    # Simplified structural model: capacity scales with material factor and inversely with height
    # P_crit = (factor * 1000) / (height ** 2) if height > 0 else 0
    capacity = (factor * 100) / (max(height, 0.5))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_capacity"],
        "load_capacity_kn": round(capacity, 2)
    }


def finalize_specs(state: State) -> dict[str, Any]:
    """Constructs the final response including metadata and calculated specs."""
    is_valid = state.get("is_valid_spec", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "engineering_data": {
            "material": state.get("material"),
            "height_m": state.get("height_meters"),
            "pressure_psi": state.get("pressure_rating_psi"),
            "rated_load_kn": state.get("load_capacity_kn")
        },
        "ok": is_valid
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specs"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("calculate_load_capacity", calculate_load_capacity)
_g.add_node("finalize_specs", finalize_specs)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "calculate_load_capacity")
_g.add_edge("calculate_load_capacity", "finalize_specs")
_g.add_edge("finalize_specs", END)

graph = _g.compile()
