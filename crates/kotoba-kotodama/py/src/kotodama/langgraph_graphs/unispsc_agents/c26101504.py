# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101504 — Diesel (segment 26).

Bespoke graph for monitoring diesel fuel quality, verifying cetane ratings,
and checking sulfur compliance for environmental standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101504"
UNISPSC_TITLE = "Diesel"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    cetane_index: float
    sulfur_content_ppm: int
    flash_point_c: int
    quality_verified: bool


def validate_fuel_spec(state: State) -> dict[str, Any]:
    """Extract and validate basic fuel properties from input data."""
    inp = state.get("input") or {}
    cetane = float(inp.get("cetane_index", 42.0))
    sulfur = int(inp.get("sulfur_ppm", 15))
    flash = int(inp.get("flash_point", 52))

    return {
        "log": [f"{UNISPSC_CODE}:validate_fuel_spec"],
        "cetane_index": cetane,
        "sulfur_content_ppm": sulfur,
        "flash_point_c": flash,
    }


def analyze_compliance(state: State) -> dict[str, Any]:
    """Verify if the diesel meets ASTM D975 or similar quality standards."""
    cetane = state.get("cetane_index", 0.0)
    sulfur = state.get("sulfur_content_ppm", 100)
    flash = state.get("flash_point_c", 0)

    # Ultra-Low Sulfur Diesel (ULSD) usually < 15ppm
    # Standard cetane usually >= 40
    # Flash point usually >= 52C
    is_compliant = cetane >= 40.0 and sulfur <= 15 and flash >= 52

    return {
        "log": [f"{UNISPSC_CODE}:analyze_compliance"],
        "quality_verified": is_compliant,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Emit the final certification manifest for the specific diesel lot."""
    verified = state.get("quality_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if verified else "REJECTED",
            "metrics": {
                "cetane": state.get("cetane_index"),
                "sulfur": state.get("sulfur_content_ppm"),
                "flash_point": state.get("flash_point_c"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_fuel_spec)
_g.add_node("analyze", analyze_compliance)
_g.add_node("certify", certify_batch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
