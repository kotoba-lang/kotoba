# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for Laser Procurement (UNISPSC 23231202).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231202"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231202"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific procurement state
    laser_power_class: int
    wavelength_nm: float
    safety_compliance_verified: bool
    vendor_certification_level: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the technical specifications for the laser procurement."""
    inp = state.get("input") or {}
    power_class = inp.get("power_class", 1)
    wavelength = inp.get("wavelength", 1064.0)

    # Simple logic to verify if parameters are within industrial norms
    specs_ok = 1 <= power_class <= 5

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications - power_class={power_class}"],
        "laser_power_class": power_class,
        "wavelength_nm": wavelength,
        "safety_compliance_verified": specs_ok
    }


def assess_safety_protocols(state: State) -> dict[str, Any]:
    """Determines safety requirements based on the laser power class."""
    power_class = state.get("laser_power_class", 1)

    if power_class >= 4:
        cert = "HIGH_POWER_INDUSTRIAL_SAFETY"
    elif power_class >= 2:
        cert = "STANDARD_LAB_SAFETY"
    else:
        cert = "GENERAL_CONSUMER_SAFETY"

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety_protocols - cert_assigned={cert}"],
        "vendor_certification_level": cert
    }


def finalize_procurement_package(state: State) -> dict[str, Any]:
    """Generates the final procurement metadata and result package."""
    is_safe = state.get("safety_compliance_verified", False)
    cert = state.get("vendor_certification_level", "NONE")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_package"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "procurement_status": "VALIDATED" if is_safe else "REQUIREMENTS_NOT_MET",
            "certification_required": cert,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("assess_safety_protocols", assess_safety_protocols)
_g.add_node("finalize_procurement_package", finalize_procurement_package)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "assess_safety_protocols")
_g.add_edge("assess_safety_protocols", "finalize_procurement_package")
_g.add_edge("finalize_procurement_package", END)

graph = _g.compile()
