# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121503 — Plastic (segment 14).
Bespoke implementation for plastic-based paper products and accessories.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121503"
UNISPSC_TITLE = "Plastic"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Plastic products in the paper/office segment
    material_type: str
    mil_thickness: float
    is_archival_safe: bool
    recycled_percentage: int


def validate_specification(state: State) -> dict[str, Any]:
    """Validates the input specifications for the plastic product batch."""
    inp = state.get("input") or {}
    # Defaulting to Polypropylene (PP) which is common for plastic office supplies
    m_type = inp.get("material", "Polypropylene")
    thickness = float(inp.get("thickness", 3.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specification"],
        "material_type": m_type,
        "mil_thickness": thickness,
    }


def assess_composition(state: State) -> dict[str, Any]:
    """Assesses archival safety and environmental metrics based on composition."""
    m_type = state.get("material_type", "Unknown")
    # PVC is generally not archival safe, while PP and PE are.
    archival = "PVC" not in m_type.upper()

    # Simulate extraction of recycled content from input or defaults
    inp = state.get("input") or {}
    recycled = int(inp.get("recycled_content", 25))

    return {
        "log": [f"{UNISPSC_CODE}:assess_composition"],
        "is_archival_safe": archival,
        "recycled_percentage": recycled,
    }


def finalize_quality_report(state: State) -> dict[str, Any]:
    """Finalizes the production quality report for the plastic commodity."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_quality_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "properties": {
                "material": state.get("material_type"),
                "thickness_mil": state.get("mil_thickness"),
                "archival_safe": state.get("is_archival_safe"),
                "recycled_content_pct": state.get("recycled_percentage"),
            },
            "status": "APPROVED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specification", validate_specification)
_g.add_node("assess_composition", assess_composition)
_g.add_node("finalize_quality_report", finalize_quality_report)

_g.add_edge(START, "validate_specification")
_g.add_edge("validate_specification", "assess_composition")
_g.add_edge("assess_composition", "finalize_quality_report")
_g.add_edge("finalize_quality_report", END)

graph = _g.compile()
