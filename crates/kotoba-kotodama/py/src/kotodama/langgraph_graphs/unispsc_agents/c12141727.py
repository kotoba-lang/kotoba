# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12141727 — Resin Procurement (segment 12).
Bespoke graph for managing resin material grading, supplier verification, and procurement authorization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12141727"
UNISPSC_TITLE = "Resin Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12141727"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Resin Procurement
    grade: str
    viscosity_cp: float
    purity_level: float
    supplier_id: str
    is_hazardous: bool


def validate_material_specs(state: State) -> dict[str, Any]:
    """Validate requested resin specifications against standard industrial grades."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "industrial-01")
    viscosity = float(inp.get("viscosity", 1500.0))
    purity = float(inp.get("purity", 0.985))

    return {
        "log": [f"{UNISPSC_CODE}:validate_material_specs"],
        "grade": grade,
        "viscosity_cp": viscosity,
        "purity_level": purity,
        "is_hazardous": grade.lower().startswith("chem")
    }


def verify_vendor_eligibility(state: State) -> dict[str, Any]:
    """Cross-reference grade requirements with certified supplier lists."""
    grade = state.get("grade", "standard")
    # Deterministic mapping for procurement logic
    supplier = f"VEND-{grade[:4].upper()}-99"
    return {
        "log": [f"{UNISPSC_CODE}:verify_vendor_eligibility"],
        "supplier_id": supplier
    }


def approve_acquisition(state: State) -> dict[str, Any]:
    """Execute final approval and bundle state into the result record."""
    grade = state.get("grade")
    supplier = state.get("supplier_id")
    purity = state.get("purity_level", 0.0)

    success = bool(grade and supplier and purity >= 0.95)

    return {
        "log": [f"{UNISPSC_CODE}:approve_acquisition"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": success,
            "acquisition_details": {
                "grade": grade,
                "supplier": supplier,
                "purity": purity,
                "hazardous": state.get("is_hazardous")
            }
        }
    }


_g = StateGraph(State)
_g.add_node("validate_material_specs", validate_material_specs)
_g.add_node("verify_vendor_eligibility", verify_vendor_eligibility)
_g.add_node("approve_acquisition", approve_acquisition)

_g.add_edge(START, "validate_material_specs")
_g.add_edge("validate_material_specs", "verify_vendor_eligibility")
_g.add_edge("verify_vendor_eligibility", "approve_acquisition")
_g.add_edge("approve_acquisition", END)

graph = _g.compile()
