# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102203 — Bearing (segment 20).
Bespoke logic for mechanical bearing specification and load validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102203"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102203"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Bearing
    bore_diameter_mm: float
    load_rating_dynamic_kn: float
    lubrication_required: bool
    quality_cert_verified: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects the bearing dimensions and certification status."""
    inp = state.get("input") or {}
    bore = float(inp.get("bore_diameter", 0.0))
    cert = inp.get("cert_id") is not None

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs: bore={bore}mm, cert={cert}"],
        "bore_diameter_mm": bore,
        "quality_cert_verified": cert,
    }


def validate_load_capacity(state: State) -> dict[str, Any]:
    """Calculates if the bearing meets dynamic load requirements."""
    inp = state.get("input") or {}
    required_load = float(inp.get("target_load_kn", 0.0))
    # Simple logic: assume 1.5x bore diameter as a mock capacity factor
    calculated_capacity = state.get("bore_diameter_mm", 0.0) * 1.5
    meets_load = calculated_capacity >= required_load

    return {
        "log": [f"{UNISPSC_CODE}:validate_load_capacity: capacity={calculated_capacity}kN, meets={meets_load}"],
        "load_rating_dynamic_kn": calculated_capacity,
        "lubrication_required": calculated_capacity > 50.0,
    }


def finalize_asset_data(state: State) -> dict[str, Any]:
    """Prepares the final result based on inspection and validation."""
    is_valid = state.get("quality_cert_verified", False) and state.get("bore_diameter_mm", 0.0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_data"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "approved" if is_valid else "pending_review",
            "specs": {
                "bore": state.get("bore_diameter_mm"),
                "capacity": state.get("load_rating_dynamic_kn"),
                "lubrication": "grease" if state.get("lubrication_required") else "sealed"
            },
            "ok": is_valid
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("validate_load_capacity", validate_load_capacity)
_g.add_node("finalize_asset_data", finalize_asset_data)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "validate_load_capacity")
_g.add_edge("validate_load_capacity", "finalize_asset_data")
_g.add_edge("finalize_asset_data", END)

graph = _g.compile()
