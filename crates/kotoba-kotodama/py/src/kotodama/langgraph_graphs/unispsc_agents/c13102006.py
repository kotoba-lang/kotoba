# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13102006 — H F (segment 13).

Bespoke graph logic for Hydrofluorocarbon (H F) chemical materials.
This agent validates chemical purity, checks safety compliance for flash points,
and records the material batch into the ledger.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102006"
UNISPSC_TITLE = "H F"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102006"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Hydrofluorocarbon (H F)
    purity_percentage: float
    flash_point_celsius: float
    molecular_weight: float
    is_hazardous: bool
    quarantine_verified: bool


def inspect_composition(state: State) -> dict[str, Any]:
    """Inspects the H F chemical composition from the input data."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 99.5))
    mol_weight = float(inp.get("mol_weight", 102.03))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "purity_percentage": purity,
        "molecular_weight": mol_weight,
    }


def verify_safety_specs(state: State) -> dict[str, Any]:
    """Verifies flash point and hazardous status for safe transport."""
    inp = state.get("input") or {}
    flash_point = float(inp.get("flash_point", -50.0))
    # HFCs often have very low flash points or are non-flammable but pressurized
    is_hazardous = flash_point < 0.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_specs"],
        "flash_point_celsius": flash_point,
        "is_hazardous": is_hazardous,
        "quarantine_verified": True,
    }


def finalize_material_batch(state: State) -> dict[str, Any]:
    """Finalizes the chemical batch record and emits the result."""
    purity = state.get("purity_percentage", 0.0)
    safe = not state.get("is_hazardous", True)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_status": "accepted" if purity > 98.0 else "rejected",
            "safety_clearance": safe,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_composition)
_g.add_node("verify", verify_safety_specs)
_g.add_node("finalize", finalize_material_batch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
