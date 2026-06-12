# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102006 — Workbench (segment 24).

Bespoke graph logic for handling workbench specifications and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102006"
UNISPSC_TITLE = "Workbench"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102006"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Workbench
    spec_compliance: bool
    load_capacity_verified: bool
    surface_finish: str
    dimensions_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validate workbench dimensions and load capacity requirements."""
    inp = state.get("input") or {}
    dims = inp.get("dimensions", {})
    load = inp.get("load_capacity_kg", 0)

    # Simple logic: require dimensions and a positive load capacity
    is_valid = bool(dims) and load > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs -> {'valid' if is_valid else 'invalid'}"],
        "spec_compliance": is_valid,
        "load_capacity_verified": load >= 250,
        "dimensions_verified": "height" in dims and "width" in dims and "depth" in dims
    }


def verify_materials(state: State) -> dict[str, Any]:
    """Verify surface materials and finish based on intended use."""
    inp = state.get("input") or {}
    surface = inp.get("surface_material", "standard_steel")
    finish = "industrial_powder_coat" if surface == "steel" else "natural_oil"

    return {
        "log": [f"{UNISPSC_CODE}:verify_materials -> {surface}"],
        "surface_finish": finish
    }


def certify_workbench(state: State) -> dict[str, Any]:
    """Final certification and result emission."""
    is_compliant = state.get("spec_compliance", False)
    is_load_ok = state.get("load_capacity_verified", False)
    is_dims_ok = state.get("dimensions_verified", False)

    certified = is_compliant and is_load_ok and is_dims_ok

    return {
        "log": [f"{UNISPSC_CODE}:certify_workbench -> {'certified' if certified else 'rejected'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": certified,
            "surface_finish": state.get("surface_finish"),
            "status": "PASS" if certified else "FAIL"
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_materials", verify_materials)
_g.add_node("certify_workbench", certify_workbench)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_materials")
_g.add_edge("verify_materials", "certify_workbench")
_g.add_edge("certify_workbench", END)

graph = _g.compile()
