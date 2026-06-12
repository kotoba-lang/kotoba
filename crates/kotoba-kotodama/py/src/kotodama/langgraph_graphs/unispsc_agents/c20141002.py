# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20141002 — Bearing (segment 20).

This bespoke implementation handles state transitions for mechanical bearing
validation, including load capacity assessment and tolerance verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141002"
UNISPSC_TITLE = "Bearing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Bearings
    load_rating_kn: float
    tolerance_class: str
    lubrication_type: str
    qc_passed: bool


def assess_load_capacity(state: State) -> dict[str, Any]:
    """Calculates or verifies the load rating for the specified bearing."""
    inp = state.get("input") or {}
    # Default to a standard baseline if not specified in input
    rating = float(inp.get("load_rating", 15.5))
    return {
        "log": [f"{UNISPSC_CODE}:assess_load_capacity"],
        "load_rating_kn": rating,
    }


def verify_tolerance_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical tolerances against industrial standards."""
    inp = state.get("input") or {}
    t_class = str(inp.get("tolerance", "ABEC-1"))
    # Simulation: high-precision classes pass QC automatically in this logic
    is_high_precision = t_class in ["ABEC-3", "ABEC-5", "ABEC-7", "P4", "P2"]
    return {
        "log": [f"{UNISPSC_CODE}:verify_tolerance_specs"],
        "tolerance_class": t_class,
        "qc_passed": is_high_precision or inp.get("force_qc", False)
    }


def initialize_catalog_entry(state: State) -> dict[str, Any]:
    """Emits the final processed state for the Bearing component."""
    inp = state.get("input") or {}
    lubricant = str(inp.get("lubricant", "Lithium Grease"))
    return {
        "log": [f"{UNISPSC_CODE}:initialize_catalog_entry"],
        "lubrication_type": lubricant,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attributes": {
                "load_rating_kn": state.get("load_rating_kn"),
                "tolerance": state.get("tolerance_class"),
                "lubrication": lubricant,
                "qc_status": "passed" if state.get("qc_passed") else "standard"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_load", assess_load_capacity)
_g.add_node("verify_tolerance", verify_tolerance_specs)
_g.add_node("catalog", initialize_catalog_entry)

_g.add_edge(START, "assess_load")
_g.add_edge("assess_load", "verify_tolerance")
_g.add_edge("verify_tolerance", "catalog")
_g.add_edge("catalog", END)

graph = _g.compile()
