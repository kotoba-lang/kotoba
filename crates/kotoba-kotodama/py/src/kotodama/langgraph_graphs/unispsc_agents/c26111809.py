# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111809 — Belt Guard.
Bespoke logic for safety component specification and compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111809"
UNISPSC_TITLE = "Belt Guard"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111809"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Belt Guard
    safety_compliance_level: str
    material_spec: str
    mesh_aperture_mm: float
    is_osha_compliant: bool


def inspect_specification(state: State) -> dict[str, Any]:
    """Inspects machine specs to determine safety guard requirements."""
    inp = state.get("input") or {}
    machine_type = inp.get("machine_type", "generic")
    belt_speed = inp.get("belt_speed_mps", 0.0)

    # Logic: Faster belts require finer mesh or solid guards
    compliance = "Standard"
    if belt_speed > 10.0:
        compliance = "High-Velocity"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specification: {machine_type} at {belt_speed}m/s"],
        "safety_compliance_level": compliance,
        "is_osha_compliant": belt_speed > 0,
    }


def configure_guard(state: State) -> dict[str, Any]:
    """Configures the material and mesh size based on compliance level."""
    level = state.get("safety_compliance_level", "Standard")

    material = "Powder-coated Carbon Steel"
    mesh_size = 12.5 # mm

    if level == "High-Velocity":
        material = "Heavy-Duty Stainless Steel"
        mesh_size = 6.0

    return {
        "log": [f"{UNISPSC_CODE}:configure_guard: {level} -> {material}"],
        "material_spec": material,
        "mesh_aperture_mm": mesh_size,
    }


def certify_design(state: State) -> dict[str, Any]:
    """Finalizes the guard design and issues the actor result."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_design"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_spec"),
                "mesh_size_mm": state.get("mesh_aperture_mm"),
                "osha_verified": state.get("is_osha_compliant"),
            },
            "status": "Certified",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specification)
_g.add_node("configure", configure_guard)
_g.add_node("certify", certify_design)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
