# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23231102 — Laser Procurement (segment 23).

This bespoke LangGraph implementation handles the procurement workflow for
industrial laser equipment, including specification validation and safety
compliance verification for high-energy optical systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23231102"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23231102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Laser Procurement
    laser_specs_valid: bool
    safety_certification_id: str
    supplier_tier: int
    procurement_authorized: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates technical specifications for the laser equipment."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    # Check for required parameters like wavelength or power output
    valid = bool(specs.get("wavelength") and specs.get("power_watts"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "laser_specs_valid": valid,
        "supplier_tier": inp.get("tier", 3)
    }


def verify_safety_compliance(state: State) -> dict[str, Any]:
    """Ensures the laser system meets industrial safety and radiation standards."""
    is_valid = state.get("laser_specs_valid", False)
    # Mock safety certification logic based on specs and tier
    cert_id = f"CERT-LSR-{UNISPSC_CODE}-001" if is_valid else "PENDING"
    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_compliance"],
        "safety_certification_id": cert_id,
        "procurement_authorized": is_valid
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Generates the final procurement record for the laser system."""
    authorized = state.get("procurement_authorized", False)
    cert_id = state.get("safety_certification_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "safety_cert": cert_id,
            "status": "AUTHORIZED" if authorized else "REJECTED",
            "ok": authorized,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specifications", validate_specifications)
_g.add_node("verify_safety_compliance", verify_safety_compliance)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "verify_safety_compliance")
_g.add_edge("verify_safety_compliance", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
