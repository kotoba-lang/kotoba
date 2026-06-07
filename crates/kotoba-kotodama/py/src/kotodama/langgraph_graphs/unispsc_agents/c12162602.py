# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12162602 — Semiconductor Material (segment 12).

Bespoke graph logic for validating and certifying semiconductor material batches,
handling purity levels, substrate types, and doping specifications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162602"
UNISPSC_TITLE = "Semiconductor Material"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162602"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Semiconductor Material
    material_type: str  # e.g., Silicon, Germanium, GaN
    purity_nines: float  # e.g., 9.99999 (6N)
    doping_profile: str  # n-type, p-type, or intrinsic
    crystal_orientation: str  # e.g., <100>, <111>
    quality_certified: bool


def inspect_batch_specs(state: State) -> dict[str, Any]:
    """Analyze the input batch specifications for material identity and orientation."""
    inp = state.get("input") or {}
    m_type = inp.get("material", "Silicon (Si)")
    orientation = inp.get("orientation", "<100>")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_batch_specs:identified_{m_type}"],
        "material_type": m_type,
        "crystal_orientation": orientation,
    }


def analyze_purity_and_doping(state: State) -> dict[str, Any]:
    """Evaluate purity levels and verify doping agent compliance."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 9.9999))
    doping = inp.get("doping", "Intrinsic")

    # Logic: High-end electronics often require 9N or higher purity
    is_high_purity = purity >= 9.99999999

    return {
        "log": [f"{UNISPSC_CODE}:analyze_purity_and_doping:{purity}N_purity"],
        "purity_nines": purity,
        "doping_profile": doping,
        "quality_certified": is_high_purity,
    }


def certify_material_grade(state: State) -> dict[str, Any]:
    """Finalize the certification result based on material properties."""
    is_certified = state.get("quality_certified", False)
    m_type = state.get("material_type")

    return {
        "log": [f"{UNISPSC_CODE}:certify_material_grade:{'approved' if is_certified else 'conditional'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certification_status": "CERTIFIED" if is_certified else "STANDARD_GRADE",
            "material_metadata": {
                "base": m_type,
                "purity": state.get("purity_nines"),
                "doping": state.get("doping_profile"),
                "orientation": state.get("crystal_orientation")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_batch_specs)
_g.add_node("analyze", analyze_purity_and_doping)
_g.add_node("certify", certify_material_grade)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
