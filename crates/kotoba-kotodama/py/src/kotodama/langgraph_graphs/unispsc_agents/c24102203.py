# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102203 — Seal (segment 24).

Bespoke logic for industrial seal verification, focusing on material
compatibility, pressure ratings, and dimensional tolerances.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102203"
UNISPSC_TITLE = "Seal"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102203"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Seal
    material_type: str
    pressure_rating_psi: float
    is_high_temp: bool
    dimensions_valid: bool


def ingest_and_validate(state: State) -> dict[str, Any]:
    """Ingests raw input and validates seal parameters."""
    inp = state.get("input") or {}
    mat = str(inp.get("material", "nitrile")).lower()
    pressure = float(inp.get("pressure_psi", 0.0))

    # Basic dimensional check: assume ID and OD are provided
    id_mm = float(inp.get("inner_diameter", 0.0))
    od_mm = float(inp.get("outer_diameter", 0.0))
    dims_ok = od_mm > id_mm > 0

    return {
        "log": [f"{UNISPSC_CODE}:ingest_and_validate: mat={mat}, pressure={pressure}"],
        "material_type": mat,
        "pressure_rating_psi": pressure,
        "dimensions_valid": dims_ok,
    }


def analyze_compatibility(state: State) -> dict[str, Any]:
    """Analyzes material compatibility and temperature thresholds."""
    mat = state.get("material_type", "nitrile")

    # Viton and Silicone are treated as high-temp materials
    high_temp = mat in ["viton", "silicone"]

    return {
        "log": [f"{UNISPSC_CODE}:analyze_compatibility: high_temp={high_temp}"],
        "is_high_temp": high_temp,
    }


def output_seal_data(state: State) -> dict[str, Any]:
    """Finalizes the Seal agent result structure."""
    dims_ok = state.get("dimensions_valid", False)
    mat = state.get("material_type", "unknown")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "verification": {
            "material": mat,
            "pressure_max": state.get("pressure_rating_psi"),
            "thermal_grade": "high" if state.get("is_high_temp") else "standard",
            "dimensional_integrity": "pass" if dims_ok else "fail",
        },
        "ok": dims_ok
    }
    return {
        "log": [f"{UNISPSC_CODE}:output_seal_data"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_and_validate)
_g.add_node("analyze", analyze_compatibility)
_g.add_node("output", output_seal_data)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "output")
_g.add_edge("output", END)

graph = _g.compile()
