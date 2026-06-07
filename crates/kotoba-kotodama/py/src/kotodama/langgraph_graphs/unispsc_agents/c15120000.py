# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15120000 — Hydrocarbon (segment 15).

Bespoke graph logic for Hydrocarbon handling, including chemical composition
analysis, purity verification, and safety assessment for energy source processing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15120000"
UNISPSC_TITLE = "Hydrocarbon"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15120000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Extra Hydrocarbon domain fields
    hydrocarbon_family: str
    purity_percentage: float
    is_volatile: bool
    flash_point_c: float


def inspect_sample(state: State) -> dict[str, Any]:
    """Inspect the raw hydrocarbon sample for its structural family."""
    inp = state.get("input") or {}
    family = inp.get("family", "saturated")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_sample"],
        "hydrocarbon_family": family,
    }


def analyze_purity(state: State) -> dict[str, Any]:
    """Determine the chemical purity of the hydrocarbon sample."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 98.5))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_purity"],
        "purity_percentage": purity,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Assess the flash point and volatility for safe transport and storage."""
    inp = state.get("input") or {}
    flash = float(inp.get("flash_point", 25.0))
    # Safety logic: high volatility if flash point is low (standard threshold ~37.8C)
    volatile = flash < 37.8
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "flash_point_c": flash,
        "is_volatile": volatile,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Package the analysis into a final result certificate."""
    purity = state.get("purity_percentage", 0.0)
    is_safe = purity > 95.0 and not state.get("is_volatile", True)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "analysis": {
                "family": state.get("hydrocarbon_family"),
                "purity": purity,
                "is_volatile": state.get("is_volatile"),
                "flash_point": state.get("flash_point_c"),
            },
            "ok": True,
            "certified": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_sample)
_g.add_node("analyze", analyze_purity)
_g.add_node("safety", verify_safety)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "safety")
_g.add_edge("safety", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
