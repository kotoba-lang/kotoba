# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142201 — Hose (segment 20).

Bespoke graph logic for hose specification validation, pressure integrity
assessment, and catalog registration. This agent processes physical
attributes specific to industrial and commercial hose products.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142201"
UNISPSC_TITLE = "Hose"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Hose
    pressure_rating_psi: int
    material_composition: str
    diameter_inches: float
    length_feet: float
    is_reinforced: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Parse and validate the physical dimensions and material of the hose."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "pressure_rating_psi": int(inp.get("pressure_psi", 150)),
        "material_composition": str(inp.get("material", "reinforced_pvc")),
        "diameter_inches": float(inp.get("diameter", 0.625)),
        "length_feet": float(inp.get("length", 50.0)),
        "is_reinforced": bool(inp.get("reinforced", True)),
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Check if the material and reinforcement support the stated pressure rating."""
    psi = state.get("pressure_rating_psi", 0)
    reinforced = state.get("is_reinforced", False)

    # Heuristic: High pressure (>300 PSI) requires reinforcement
    integrity_status = "nominal"
    if psi > 300 and not reinforced:
        integrity_status = "integrity_warning_low_reinforcement"
    elif psi > 1000:
        integrity_status = "heavy_duty"

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity (status={integrity_status})"]
    }


def register_catalog(state: State) -> dict[str, Any]:
    """Finalize the hose record for the asset registry."""
    return {
        "log": [f"{UNISPSC_CODE}:register_catalog"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attributes": {
                "material": state.get("material_composition"),
                "max_pressure": f"{state.get('pressure_rating_psi')} PSI",
                "size": f"{state.get('diameter_inches')} in x {state.get('length_feet')} ft"
            },
            "compliance": {
                "certified": True,
                "tier": "industrial" if state.get("pressure_rating_psi", 0) > 500 else "commercial"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("verify_integrity", verify_integrity)
_g.add_node("register_catalog", register_catalog)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "verify_integrity")
_g.add_edge("verify_integrity", "register_catalog")
_g.add_edge("register_catalog", END)

graph = _g.compile()
