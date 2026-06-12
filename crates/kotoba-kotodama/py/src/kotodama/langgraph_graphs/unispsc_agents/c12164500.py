# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12164500 —  (segment 12).

Bespoke graph for animal housing and accessories, handling structural
safety and habitability validation for the Etz Hayyim supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12164500"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12164500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Segment 12 supplies
    material_safety_verified: bool
    structural_integrity_score: float
    ventilation_verified: bool
    dimensions_match: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Inspects the physical specifications of the housing unit."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    material = inp.get("material", "unknown")

    # Simple logic to simulate domain verification
    is_safe = material.lower() not in ["lead", "toxic_plastic"]
    has_dims = bool(dims.get("length") and dims.get("width"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_safety_verified": is_safe,
        "dimensions_match": has_dims,
    }


def assess_safety(state: State) -> dict[str, Any]:
    """Evaluates the structural safety and environmental factors."""
    inp = state.get("input") or {}
    airflow = inp.get("airflow_cfm", 0)
    load_test = inp.get("load_bearing_kg", 0)

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety"],
        "ventilation_verified": airflow > 10,
        "structural_integrity_score": min(1.0, load_test / 50.0) if load_test > 0 else 0.0,
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Finalizes the certification of the housing or accessory item."""
    safety_ok = state.get("material_safety_verified", False)
    struct_ok = state.get("structural_integrity_score", 0.0) > 0.5

    is_certified = safety_ok and struct_ok

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if is_certified else "rejected",
            "metadata": {
                "material_integrity": safety_ok,
                "structural_score": state.get("structural_integrity_score", 0.0)
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("assess_safety", assess_safety)
_g.add_node("certify_unit", certify_unit)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "assess_safety")
_g.add_edge("assess_safety", "certify_unit")
_g.add_edge("certify_unit", END)

graph = _g.compile()
