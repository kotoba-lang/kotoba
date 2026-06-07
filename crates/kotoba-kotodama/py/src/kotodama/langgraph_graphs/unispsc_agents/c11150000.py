# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11150000 — Raw Material.
Bespoke graph for processing raw material extraction and quality control metadata.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11150000"
UNISPSC_TITLE = "Raw Material"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11150000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Raw Material
    material_grade: str
    origin_verified: bool
    purity_index: float
    safety_certified: bool


def inspect_material(state: State) -> dict[str, Any]:
    """Analyzes material grade and purity from input data."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "standard")
    purity = inp.get("purity", 1.0)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_material"],
        "material_grade": grade,
        "purity_index": purity,
    }


def verify_provenance(state: State) -> dict[str, Any]:
    """Validates the origin and safety certifications of the raw material."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:verify_provenance"],
        "origin_verified": "origin" in inp,
        "safety_certified": inp.get("certified", False),
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Finalizes the batch record for inventory systems."""
    is_valid = state.get("origin_verified", False) and state.get("purity_index", 0) > 0.7
    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "grade": state.get("material_grade"),
            "status": "ready_for_production" if is_valid else "quarantined",
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_material", inspect_material)
_g.add_node("verify_provenance", verify_provenance)
_g.add_node("finalize_batch", finalize_batch)

_g.add_edge(START, "inspect_material")
_g.add_edge("inspect_material", "verify_provenance")
_g.add_edge("verify_provenance", "finalize_batch")
_g.add_edge("finalize_batch", END)

graph = _g.compile()
