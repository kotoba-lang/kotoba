# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241503 — Component (segment 23).
Bespoke logic for industrial component validation and material verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241503"
UNISPSC_TITLE = "Component"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for "Component"
    component_id: str
    material_spec: str
    is_compliant: bool
    dimensions_verified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the mechanical specifications of the component."""
    inp = state.get("input") or {}
    comp_id = inp.get("id", "unknown-part")
    dims = inp.get("dimensions", {})
    # Simple check for required dimension keys
    verified = "width" in dims and "height" in dims

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs:{comp_id}"],
        "component_id": comp_id,
        "dimensions_verified": verified
    }


def verify_material(state: State) -> dict[str, Any]:
    """Verifies the material composition against industrial standards."""
    inp = state.get("input") or {}
    material = inp.get("material", "standard-alloy")
    # Simulation: assume compliance if material starts with 'ASTM' or is the default
    compliant = material.startswith("ASTM") or material == "standard-alloy"

    return {
        "log": [f"{UNISPSC_CODE}:verify_material:{material}"],
        "material_spec": material,
        "is_compliant": compliant
    }


def finalize_component(state: State) -> dict[str, Any]:
    """Finalizes the component processing and generates the result record."""
    is_ok = state.get("dimensions_verified", False) and state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_component:success={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "component_id": state.get("component_id"),
            "status": "certified" if is_ok else "rejected",
            "verified": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_material", verify_material)
_g.add_node("finalize_component", finalize_component)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_material")
_g.add_edge("verify_material", "finalize_component")
_g.add_edge("finalize_component", END)

graph = _g.compile()
