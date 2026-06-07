# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101705 — Clamp (segment 22).

This agent provides a bespoke graph-based workflow for validating and
certifying structural clamps within the building and construction segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101705"
UNISPSC_TITLE = "Clamp"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101705"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields
    clamp_type: str  # e.g., C-clamp, Bar clamp, Pipe clamp
    pressure_rating_psi: float
    material_spec: str
    safety_certified: bool


def analyze_spec(state: State) -> dict[str, Any]:
    """Extracts and analyzes the technical specifications of the clamp."""
    inp = state.get("input") or {}
    clamp_type = inp.get("type", "standard")
    pressure = float(inp.get("pressure", 500.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_spec -> type:{clamp_type}"],
        "clamp_type": clamp_type,
        "pressure_rating_psi": pressure,
        "material_spec": inp.get("material", "carbon_steel"),
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Verifies if the pressure rating meets safety thresholds for construction."""
    pressure = state.get("pressure_rating_psi", 0.0)
    is_safe = pressure >= 300.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity -> safety_certified:{is_safe}"],
        "safety_certified": is_safe,
    }


def generate_certificate(state: State) -> dict[str, Any]:
    """Finalizes the process by generating a digital certification result."""
    is_safe = state.get("safety_certified", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "clamp_metadata": {
                "type": state.get("clamp_type"),
                "material": state.get("material_spec"),
                "max_psi": state.get("pressure_rating_psi"),
            },
            "status": "APPROVED" if is_safe else "REJECTED",
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_spec", analyze_spec)
_g.add_node("verify_integrity", verify_integrity)
_g.add_node("generate_certificate", generate_certificate)

_g.add_edge(START, "analyze_spec")
_g.add_edge("analyze_spec", "verify_integrity")
_g.add_edge("verify_integrity", "generate_certificate")
_g.add_edge("generate_certificate", END)

graph = _g.compile()
