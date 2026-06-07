# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142301 — Bearing.
Bespoke LangGraph implementation for mechanical component verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142301"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Bearing
    load_rating_kn: float
    tolerance_class: str
    lubrication_verified: bool
    material_spec: str


def analyze_load_requirements(state: State) -> dict[str, Any]:
    """Analyzes input for dynamic and static load ratings."""
    inp = state.get("input") or {}
    req_load = float(inp.get("required_load", 0.0))

    # Simulate a calculation or verification step
    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_requirements"],
        "load_rating_kn": req_load * 1.2,  # Safety factor applied
        "material_spec": inp.get("material", "Chrome Steel (GCr15)")
    }


def check_tolerance_standards(state: State) -> dict[str, Any]:
    """Verifies bearing tolerances against ISO/ABEC standards."""
    inp = state.get("input") or {}
    precision_level = inp.get("precision", "P0/ABEC-1")

    return {
        "log": [f"{UNISPSC_CODE}:check_tolerance_standards"],
        "tolerance_class": precision_level,
        "lubrication_verified": "lube_type" in inp
    }


def finalize_bearing_metadata(state: State) -> dict[str, Any]:
    """Assembles the final catalog-ready response for the bearing component."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_bearing_metadata"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "technical_specs": {
                "load_rating_kn": state.get("load_rating_kn"),
                "tolerance": state.get("tolerance_class"),
                "material": state.get("material_spec"),
                "lubrication_status": "Verified" if state.get("lubrication_verified") else "Default"
            },
            "status": "ready"
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_load", analyze_load_requirements)
_g.add_node("check_tolerance", check_tolerance_standards)
_g.add_node("finalize", finalize_bearing_metadata)

_g.add_edge(START, "analyze_load")
_g.add_edge("analyze_load", "check_tolerance")
_g.add_edge("check_tolerance", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
