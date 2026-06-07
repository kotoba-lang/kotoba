# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121515 —  (segment 15).
Bespoke logic for lubricant and fuel additive specification validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121515"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121515"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    viscosity_index: float
    flash_point_c: float
    purity_level: float
    is_compliant: bool


def analyze_specifications(state: State) -> dict[str, Any]:
    """Analyzes the input lubricant parameters for industrial grade compliance."""
    inp = state.get("input") or {}
    viscosity = float(inp.get("viscosity", 100.0))
    flash_point = float(inp.get("flash_point", 220.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_specifications(v={viscosity}, fp={flash_point})"],
        "viscosity_index": viscosity,
        "flash_point_c": flash_point,
    }


def verify_purity(state: State) -> dict[str, Any]:
    """Performs a simulated chemical purity check on the sample."""
    vi = state.get("viscosity_index", 0.0)
    fp = state.get("flash_point_c", 0.0)

    # Heuristic for lubricant quality in segment 15
    purity = min(100.0, (vi * 0.4) + (fp * 0.25))
    compliant = vi >= 90.0 and fp >= 200.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_purity(score={purity:.2f}, compliant={compliant})"],
        "purity_level": purity,
        "is_compliant": compliant,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Finalizes the actor's response with compliance status and metadata."""
    purity = state.get("purity_level", 0.0)
    compliant = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "purity_level": purity,
            "compliance_status": "CERTIFIED" if compliant else "REJECTED",
            "ok": compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_specifications", analyze_specifications)
_g.add_node("verify_purity", verify_purity)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "analyze_specifications")
_g.add_edge("analyze_specifications", "verify_purity")
_g.add_edge("verify_purity", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
