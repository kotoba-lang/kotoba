# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10111303 — Fertilizer (segment 10).
Bespoke implementation for agricultural nutrient management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10111303"
UNISPSC_TITLE = "Fertilizer"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10111303"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fertilizer
    nutrient_ratio_npk: str
    moisture_content: float
    is_organic: bool
    safety_compliance_verified: bool
    batch_id: str


def inspect_composition(state: State) -> dict[str, Any]:
    """Analyzes the fertilizer composition for NPK ratio and moisture."""
    inp = state.get("input") or {}
    npk = inp.get("npk", "10-10-10")
    moisture = float(inp.get("moisture", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "nutrient_ratio_npk": npk,
        "moisture_content": moisture,
        "batch_id": f"FERT-{UNISPSC_CODE}-2026-B1",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Verifies safety standards and organic certification status."""
    inp = state.get("input") or {}
    organic = bool(inp.get("organic", False))
    # Synthetic check: moisture above 15% fails base compliance in this mock logic
    moisture = state.get("moisture_content", 0.0)
    compliance = moisture < 15.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "is_organic": organic,
        "safety_compliance_verified": compliance,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final distribution manifest and certification result."""
    safe = state.get("safety_compliance_verified", False)
    organic = state.get("is_organic", False)
    npk = state.get("nutrient_ratio_npk", "N/A")

    status = "CERTIFIED" if safe else "REJECTED_MOISTURE_HIGH"
    label = f"{npk} {'Organic' if organic else 'Mineral'} Fertilizer"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_id"),
            "status": status,
            "label": label,
            "ok": safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_composition", inspect_composition)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
