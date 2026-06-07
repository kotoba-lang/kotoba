# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101600 — Lifting Spec (segment 24).

Bespoke logic for material handling lifting specifications, ensuring
structural load integrity and safety factor compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101600"
UNISPSC_TITLE = "Lifting Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Lifting Spec
    load_limit_tonnes: float
    safety_margin: float
    spec_type: str
    inspection_required: bool


def ingest_and_validate(state: State) -> dict[str, Any]:
    """Ingests raw input and validates basic lifting parameters."""
    inp = state.get("input") or {}
    limit = float(inp.get("limit", 1.0))
    stype = str(inp.get("type", "standard_hoist"))

    return {
        "log": [f"{UNISPSC_CODE}:ingest_and_validate"],
        "load_limit_tonnes": limit,
        "spec_type": stype,
    }


def calculate_safety_profile(state: State) -> dict[str, Any]:
    """Calculates the safety margin and determines if inspection is needed."""
    limit = state.get("load_limit_tonnes", 0.0)
    # Higher loads require higher safety margins and mandatory inspection
    margin = 2.5 if limit < 5.0 else 4.0
    needs_inspect = limit > 10.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_safety_profile"],
        "safety_margin": margin,
        "inspection_required": needs_inspect,
    }


def output_lifting_spec(state: State) -> dict[str, Any]:
    """Finalizes the Lifting Spec data structure."""
    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "spec": {
            "type": state.get("spec_type"),
            "working_load_limit": state.get("load_limit_tonnes"),
            "safety_factor": state.get("safety_margin"),
            "inspection_status": "required" if state.get("inspection_required") else "optional",
        },
        "verified": True
    }
    return {
        "log": [f"{UNISPSC_CODE}:output_lifting_spec"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate", ingest_and_validate)
_g.add_node("profile", calculate_safety_profile)
_g.add_node("output", output_lifting_spec)

_g.add_edge(START, "validate")
_g.add_edge("validate", "profile")
_g.add_edge("profile", "output")
_g.add_edge("output", END)

graph = _g.compile()
