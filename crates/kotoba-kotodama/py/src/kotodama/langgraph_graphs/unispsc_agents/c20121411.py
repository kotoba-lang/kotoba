# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121411 — Fastener (segment 20).

Bespoke logic for managing fastener quality control, material verification,
 and structural load capacity calculations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121411"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121411"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Fastener
    material_grade: str
    dimensions_verified: bool
    tensile_strength_kn: float
    corrosion_resistant: bool


def verify_material_specs(state: State) -> dict[str, Any]:
    """Validates the fastener material and dimensional specifications."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    thread_spec = inp.get("thread_spec", "Metric")

    # Validation logic: Fasteners must specify thread standards
    is_valid = bool(thread_spec)

    return {
        "log": [f"{UNISPSC_CODE}:verify_material_specs:material={material}"],
        "material_grade": material,
        "dimensions_verified": is_valid,
    }


def calculate_load_rating(state: State) -> dict[str, Any]:
    """Calculates theoretical load capacity based on material grade."""
    grade = state.get("material_grade", "Standard")
    # Mock calculation logic: Stainless/Grade 8 gets higher ratings
    if "Stainless" in str(grade) or "Grade 8" in str(grade):
        rating = 45.5
        resistant = True
    else:
        rating = 22.0
        resistant = False

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_rating:kN={rating}"],
        "tensile_strength_kn": rating,
        "corrosion_resistant": resistant,
    }


def finalize_quality_report(state: State) -> dict[str, Any]:
    """Finalizes the fastener record with inspection results."""
    verified = state.get("dimensions_verified", False)
    load = state.get("tensile_strength_kn", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_quality_report:load={load}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if verified and load > 0 else "REJECTED",
            "load_rating_kn": load,
            "corrosion_resistant": state.get("corrosion_resistant"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_material", verify_material_specs)
_g.add_node("calculate_load", calculate_load_rating)
_g.add_node("finalize_report", finalize_quality_report)

_g.add_edge(START, "verify_material")
_g.add_edge("verify_material", "calculate_load")
_g.add_edge("calculate_load", "finalize_report")
_g.add_edge("finalize_report", END)

graph = _g.compile()
