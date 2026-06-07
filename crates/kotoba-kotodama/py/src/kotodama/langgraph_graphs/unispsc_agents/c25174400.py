# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174400 — Interior (segment 25).
Bespoke logic for vehicle interior component management and configuration.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174400"
UNISPSC_TITLE = "Interior"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Vehicle Interior
    vehicle_model_id: str
    upholstery_spec: str
    safety_compliance_checks: list[str]
    cabin_dimensions_verified: bool


def validate_interior_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the vehicle interior."""
    inp = state.get("input") or {}
    model_id = inp.get("vehicle_model_id", "GENERIC-V1")

    # Simulate verification of cabin dimensions
    dims_ok = "dimensions" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_interior_specs"],
        "vehicle_model_id": model_id,
        "cabin_dimensions_verified": dims_ok,
        "safety_compliance_checks": ["fire_retardancy", "airbag_clearance"],
    }


def configure_cabin_components(state: State) -> dict[str, Any]:
    """Configures specific cabin components like upholstery and seating."""
    inp = state.get("input") or {}
    style = inp.get("trim_level", "Standard")

    upholstery = "Premium Leather" if style == "Luxury" else "Industrial Fabric"

    return {
        "log": [f"{UNISPSC_CODE}:configure_cabin_components"],
        "upholstery_spec": upholstery,
    }


def finalize_interior_manifest(state: State) -> dict[str, Any]:
    """Generates the final manifest for the interior assembly."""
    compliance = state.get("safety_compliance_checks", [])
    verified = state.get("cabin_dimensions_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_interior_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vehicle_id": state.get("vehicle_model_id"),
            "upholstery": state.get("upholstery_spec"),
            "compliance_status": "Certified" if verified and compliance else "Pending",
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_interior_specs)
_g.add_node("configure", configure_cabin_components)
_g.add_node("finalize", finalize_interior_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
