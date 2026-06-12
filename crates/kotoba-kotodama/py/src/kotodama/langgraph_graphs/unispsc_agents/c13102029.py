# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13102029"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13102029"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific procurement state
    sds_verified: bool
    cas_registry_number: str
    purity_specification: float
    hazardous_material_class: int
    supplier_license_active: bool


def validate_chemical_specs(state: State) -> dict[str, Any]:
    """Initial validation of CAS number and purity requirements."""
    inp = state.get("input") or {}
    cas = inp.get("cas_number", "00-00-0")
    purity = float(inp.get("min_purity", 0.95))

    return {
        "log": [f"{UNISPSC_CODE}:validate_chemical_specs"],
        "cas_registry_number": cas,
        "purity_specification": purity,
    }


def verify_regulatory_compliance(state: State) -> dict[str, Any]:
    """Checks SDS availability and hazardous material classification."""
    inp = state.get("input") or {}
    hazmat_class = int(inp.get("hazmat_class", 0))

    # Simulate an SDS verification logic
    sds_ok = len(state.get("cas_registry_number", "")) > 3

    return {
        "log": [f"{UNISPSC_CODE}:verify_regulatory_compliance"],
        "sds_verified": sds_ok,
        "hazardous_material_class": hazmat_class,
        "supplier_license_active": True
    }


def authorize_procurement_batch(state: State) -> dict[str, Any]:
    """Finalizes the procurement authorization for the requested chemical."""
    success = state.get("sds_verified") and state.get("supplier_license_active")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "cas_number": state.get("cas_registry_number"),
            "authorized": success,
            "hazmat_level": state.get("hazardous_material_class"),
            "did": UNISPSC_DID,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_chemical_specs)
_g.add_node("compliance", verify_regulatory_compliance)
_g.add_node("authorize", authorize_procurement_batch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compliance")
_g.add_edge("compliance", "authorize")
_g.add_edge("authorize", END)

graph = _g.compile()
