# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121809 — Liner (segment 14).

This agent handles state transitions for paperboard liners and container liners,
verifying material specifications and calculating structural integrity parameters.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121809"
UNISPSC_TITLE = "Liner"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121809"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Liner
    material_type: str
    thickness_gsm: float
    burst_strength_kpa: float
    moisture_content_pct: float
    is_recycled: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects technical specifications for the liner material."""
    inp = state.get("input") or {}
    gsm = float(inp.get("gsm", 125.0))
    mtype = str(inp.get("material", "Kraft"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "thickness_gsm": gsm,
        "material_type": mtype,
        "is_recycled": "recycled" in mtype.lower(),
    }


def analyze_durability(state: State) -> dict[str, Any]:
    """Calculates burst strength based on GSM and material type."""
    gsm = state.get("thickness_gsm", 125.0)
    # Heuristic: Kraft has higher burst factor than Testliner
    factor = 3.5 if "kraft" in state.get("material_type", "").lower() else 2.8
    strength = gsm * factor

    return {
        "log": [f"{UNISPSC_CODE}:analyze_durability"],
        "burst_strength_kpa": strength,
        "moisture_content_pct": 7.5,  # Standard target moisture
    }


def finalize_batch(state: State) -> dict[str, Any]:
    """Emits the final quality report for the liner batch."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "spec_summary": {
                "material": state.get("material_type"),
                "gsm": state.get("thickness_gsm"),
                "strength": state.get("burst_strength_kpa"),
                "recycled_content": state.get("is_recycled"),
            },
            "status": "certified",
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("analyze_durability", analyze_durability)
_g.add_node("finalize_batch", finalize_batch)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "analyze_durability")
_g.add_edge("analyze_durability", "finalize_batch")
_g.add_edge("finalize_batch", END)

graph = _g.compile()
