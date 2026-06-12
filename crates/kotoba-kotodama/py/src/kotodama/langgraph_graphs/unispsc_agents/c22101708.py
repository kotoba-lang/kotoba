# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101708 — Laser Procurement (segment 22).

Bespoke graph for laser equipment acquisition, handling technical specification
validation, safety certification verification, and vendor shortlisting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101708"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101708"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Laser Procurement
    specs_validated: bool
    safety_class: str
    requires_radiation_shielding: bool
    supplier_pool: list[str]


def validate_specifications(state: State) -> dict[str, Any]:
    """Check laser technical requirements and assign safety classification."""
    inp = state.get("input") or {}
    power_watts = inp.get("power_output", 0)
    wavelength = inp.get("wavelength_nm", 0)

    # Basic safety classification logic
    safety = "Class 1"
    if power_watts > 0.5:
        safety = "Class 4"
    elif power_watts > 0.005:
        safety = "Class 3B"

    valid = power_watts > 0 and wavelength > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "specs_validated": valid,
        "safety_class": safety,
        "requires_radiation_shielding": safety in ["Class 3B", "Class 4"]
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Ensure procurement meets optical safety and shielding standards."""
    if not state.get("specs_validated"):
        return {"log": [f"{UNISPSC_CODE}:compliance_skipped_invalid_specs"]}

    shielding = state.get("requires_radiation_shielding", False)
    compliance_msg = "Shielding protocols engaged" if shielding else "Standard safety suffices"

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance({compliance_msg})"],
        "supplier_pool": ["OptoCore Systems", "LuminaTech Industries", "RayBound Solutions"]
    }


def compile_procurement_package(state: State) -> dict[str, Any]:
    """Finalize the procurement request with all technical metadata."""
    pool = state.get("supplier_pool", [])
    is_valid = state.get("specs_validated", False)

    return {
        "log": [f"{UNISPSC_CODE}:compile_procurement_package"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "meta": {
                "safety_class": state.get("safety_class"),
                "shielding_required": state.get("requires_radiation_shielding"),
                "qualified_vendors": pool
            },
            "ok": is_valid and len(pool) > 0,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("compliance", verify_compliance)
_g.add_node("compile", compile_procurement_package)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compliance")
_g.add_edge("compliance", "compile")
_g.add_edge("compile", END)

graph = _g.compile()
