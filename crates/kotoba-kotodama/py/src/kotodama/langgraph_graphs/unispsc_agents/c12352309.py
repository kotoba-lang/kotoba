# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352309 — Adhesive (segment 12).

Bespoke LangGraph implementation for Adhesive materials, focusing on
viscosity validation, curing profile assessment, and material safety
data sheet (MSDS) compliance for chemical bonding agents.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352309"
UNISPSC_TITLE = "Adhesive"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352309"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Adhesives
    viscosity_cps: int
    curing_time_minutes: int
    msds_verified: bool
    substrate_compatibility: list[str]


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical properties and safety compliance of the adhesive."""
    inp = state.get("input") or {}
    viscosity = inp.get("viscosity", 1500)
    msds_ref = inp.get("msds_reference")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications - Viscosity: {viscosity}cP"],
        "viscosity_cps": viscosity,
        "msds_verified": msds_ref is not None,
    }


def analyze_application(state: State) -> dict[str, Any]:
    """Analyzes curing requirements and substrate bonding capability."""
    # Logic to determine curing profile based on viscosity and input
    is_high_viscosity = state.get("viscosity_cps", 0) > 2000
    curing_time = 60 if is_high_viscosity else 30

    return {
        "log": [f"{UNISPSC_CODE}:analyze_application - Curing profile established"],
        "curing_time_minutes": curing_time,
        "substrate_compatibility": ["Metal", "Plastic", "Wood"] if not is_high_viscosity else ["Concrete", "Masonry"],
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Compiles the final adhesive property record for the registry."""
    msds_status = "Verified" if state.get("msds_verified") else "Pending"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record - Status: {msds_status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "properties": {
                "viscosity": state.get("viscosity_cps"),
                "curing_time": state.get("curing_time_minutes"),
                "msds_status": msds_status,
                "compatible_substrates": state.get("substrate_compatibility"),
            },
            "status": "active"
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("analyze", analyze_application)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
