# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20131304 — Bearing (segment 20).

Bespoke logic for bearing specification validation and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20131304"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20131304"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    inner_diameter_mm: float
    outer_diameter_mm: float
    load_capacity_kn: float
    is_lubricated: bool
    spec_verification: bool


def inspect_dimensions(state: State) -> dict[str, Any]:
    """Inspects physical dimensions of the bearing."""
    inp = state.get("input") or {}
    inner = float(inp.get("inner_diameter", 0.0))
    outer = float(inp.get("outer_diameter", 0.0))
    valid = inner > 0 and outer > inner
    return {
        "log": [f"{UNISPSC_CODE}:inspect_dimensions"],
        "inner_diameter_mm": inner,
        "outer_diameter_mm": outer,
        "spec_verification": valid,
    }


def verify_load_rating(state: State) -> dict[str, Any]:
    """Verifies the dynamic load capacity."""
    inp = state.get("input") or {}
    load = float(inp.get("load_rating", 0.0))
    meets_requirements = load > 0
    return {
        "log": [f"{UNISPSC_CODE}:verify_load_rating"],
        "load_capacity_kn": load,
        "spec_verification": state.get("spec_verification", False) and meets_requirements,
    }


def certify_bearing(state: State) -> dict[str, Any]:
    """Final certification of the bearing component."""
    inp = state.get("input") or {}
    lubricated = bool(inp.get("lubricated", False))
    verified = state.get("spec_verification", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_bearing"],
        "is_lubricated": lubricated,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "certified": verified,
            "spec_summary": {
                "id_mm": state.get("inner_diameter_mm"),
                "od_mm": state.get("outer_diameter_mm"),
                "load_kn": state.get("load_capacity_kn"),
                "lubricated": lubricated,
            },
            "did": UNISPSC_DID,
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_dimensions", inspect_dimensions)
_g.add_node("verify_load_rating", verify_load_rating)
_g.add_node("certify_bearing", certify_bearing)
_g.add_edge(START, "inspect_dimensions")
_g.add_edge("inspect_dimensions", "verify_load_rating")
_g.add_edge("verify_load_rating", "certify_bearing")
_g.add_edge("certify_bearing", END)

graph = _g.compile()
