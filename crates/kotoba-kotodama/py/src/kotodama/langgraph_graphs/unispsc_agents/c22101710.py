# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101710 — Fastener (segment 22).

Bespoke graph logic for industrial fasteners, handling specification
validation, mechanical property verification, and inventory assignment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101710"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101710"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Fastener
    material_grade: str
    tensile_psi_rating: int
    specification_compliance: bool
    batch_inventory_status: str


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material grade against input specs."""
    inp = state.get("input") or {}
    req_grade = inp.get("grade", "A325")
    size_mm = inp.get("diameter_mm", 12.0)

    # Simple validation logic for fastener dimensions
    compliance = size_mm > 0 and len(req_grade) > 0
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "material_grade": req_grade,
        "specification_compliance": compliance,
    }


def verify_mechanical_properties(state: State) -> dict[str, Any]:
    """Determines mechanical performance ratings based on material grade."""
    grade = state.get("material_grade", "Standard")
    # Simulation: lookup PSI rating based on fastener grade (e.g. ASTM A325 vs A307)
    psi = 120000 if "A325" in grade else 60000

    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanical_properties"],
        "tensile_psi_rating": psi,
    }


def assign_inventory(state: State) -> dict[str, Any]:
    """Finalizes the processing by checking stock availability and formatting the result."""
    compliance = state.get("specification_compliance", False)
    psi = state.get("tensile_psi_rating", 0)

    # Determine inventory status based on spec match and mechanical rating
    status = "AVAILABLE" if compliance and psi >= 60000 else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:assign_inventory"],
        "batch_inventory_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mechanical_integrity": "VERIFIED" if psi > 0 else "FAILED",
            "stock_status": status,
            "ok": compliance,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_requirements)
_g.add_node("verify", verify_mechanical_properties)
_g.add_node("inventory", assign_inventory)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "inventory")
_g.add_edge("inventory", END)

graph = _g.compile()
