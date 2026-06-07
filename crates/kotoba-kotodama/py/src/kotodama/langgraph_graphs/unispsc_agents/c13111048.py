# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c13111048 — Ore (segment 13).

Bespoke graph logic for mineral ore processing and valuation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111048"
UNISPSC_TITLE = "Ore"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111048"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Ore
    mineral_type: str
    purity_grade: float
    moisture_content: float
    assay_verified: bool


def inspect_raw_ore(state: State) -> dict[str, Any]:
    """Examines input data for mineral composition and quality markers."""
    inp = state.get("input") or {}
    mineral = inp.get("mineral", "Iron")
    grade = float(inp.get("grade", 0.65))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_ore -> {mineral} at {grade*100}% purity"],
        "mineral_type": mineral,
        "purity_grade": grade,
        "moisture_content": float(inp.get("moisture", 0.05)),
    }


def verify_assay(state: State) -> dict[str, Any]:
    """Validates the purity grade against industry standards for the mineral type."""
    grade = state.get("purity_grade", 0.0)
    # Simple threshold logic: ores below 20% are considered low grade
    verified = grade >= 0.20

    return {
        "log": [f"{UNISPSC_CODE}:verify_assay -> status: {verified}"],
        "assay_verified": verified,
    }


def calculate_yield(state: State) -> dict[str, Any]:
    """Calculates final yield and prepares the output manifest."""
    grade = state.get("purity_grade", 0.0)
    moisture = state.get("moisture_content", 0.0)
    mineral = state.get("mineral_type", "Unknown")

    # Dry weight calculation
    dry_yield = (1.0 - moisture) * grade

    return {
        "log": [f"{UNISPSC_CODE}:calculate_yield -> {dry_yield:.2f} net unit yield"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mineral": mineral,
            "net_yield": round(dry_yield, 4),
            "status": "Commercial Grade" if grade > 0.5 else "Industrial Grade",
            "ok": state.get("assay_verified", False),
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_raw_ore)
_g.add_node("verify", verify_assay)
_g.add_node("calculate", calculate_yield)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "calculate")
_g.add_edge("calculate", END)

graph = _g.compile()
