# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121901 — Material (segment 14).
Bespoke logic for industrial paper material specification and verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121901"
UNISPSC_TITLE = "Material"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121901"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Industrial Paper Materials
    material_grade: str
    weight_gsm: float
    moisture_content_pct: float
    is_recycled: bool
    spec_verified: bool


def verify_specs(state: State) -> dict[str, Any]:
    """Verify input specifications for industrial paper material."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Industrial-A")
    weight = float(inp.get("weight", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:verify_specs"],
        "material_grade": grade,
        "weight_gsm": weight,
        "spec_verified": weight > 0 and len(grade) > 0,
    }


def analyze_quality(state: State) -> dict[str, Any]:
    """Calculate material properties and quality metrics."""
    inp = state.get("input") or {}
    moisture = float(inp.get("moisture", 5.0))
    recycled = bool(inp.get("recycled", False))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_quality"],
        "moisture_content_pct": moisture,
        "is_recycled": recycled,
    }


def finalize_material_record(state: State) -> dict[str, Any]:
    """Emit the final material validation record."""
    is_valid = state.get("spec_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_material_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "material_summary": {
                "grade": state.get("material_grade"),
                "gsm": state.get("weight_gsm"),
                "recycled": state.get("is_recycled"),
                "moisture": state.get("moisture_content_pct"),
            },
            "status": "APPROVED" if is_valid else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specs", verify_specs)
_g.add_node("analyze_quality", analyze_quality)
_g.add_node("finalize_material_record", finalize_material_record)

_g.add_edge(START, "verify_specs")
_g.add_edge("verify_specs", "analyze_quality")
_g.add_edge("analyze_quality", "finalize_material_record")
_g.add_edge("finalize_material_record", END)

graph = _g.compile()
