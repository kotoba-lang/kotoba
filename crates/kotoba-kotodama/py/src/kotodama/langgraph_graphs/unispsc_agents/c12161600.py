# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12161600 — Chemical Procurement (segment 12).

Bespoke graph logic for chemical procurement workflows, including safety
compliance verification, hazard classification, and storage requirement assessment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12161600"
UNISPSC_TITLE = "Chemical Procurement"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12161600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Chemical Procurement
    sds_verified: bool
    hazard_class: str
    storage_protocol: str
    purity_specification: float


def validate_chemical_safety(state: State) -> dict[str, Any]:
    """Verify Safety Data Sheet (SDS) presence and extract hazard profile."""
    inp = state.get("input") or {}
    chemical_name = inp.get("chemical_name", "generic_reagent")

    # Simulate extraction of hazard data from input
    hazard_class = inp.get("hazard_class", "Non-Hazardous")
    has_sds = "sds_uri" in inp or "sds_content" in inp

    return {
        "log": [f"{UNISPSC_CODE}:validate_chemical_safety:{chemical_name}"],
        "sds_verified": has_sds,
        "hazard_class": hazard_class,
    }


def determine_handling_requirements(state: State) -> dict[str, Any]:
    """Assess storage and handling protocols based on hazard classification."""
    h_class = state.get("hazard_class", "Non-Hazardous")

    # Logic-based storage assignment
    if h_class == "Flammable":
        storage = "Explosion-Proof Cabinet (Class I)"
    elif h_class == "Corrosive":
        storage = "Acid-Resistant Secondary Containment"
    elif h_class == "Toxic":
        storage = "Ventilated Hazardous Material Locker"
    else:
        storage = "General Temperature-Controlled Storage"

    return {
        "log": [f"{UNISPSC_CODE}:determine_handling_requirements:{h_class}"],
        "storage_protocol": storage,
        "purity_specification": 0.999,  # High purity default for procurement
    }


def authorize_procurement_batch(state: State) -> dict[str, Any]:
    """Generate final procurement authorization with integrated safety metadata."""
    is_safe = state.get("sds_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:authorize_procurement_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "authorization_status": "CERTIFIED" if is_safe else "PENDING_SAFETY_DOCS",
            "safety": {
                "hazard_class": state.get("hazard_class"),
                "storage": state.get("storage_protocol"),
                "purity_min": state.get("purity_specification"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_chemical_safety", validate_chemical_safety)
_g.add_node("determine_handling_requirements", determine_handling_requirements)
_g.add_node("authorize_procurement_batch", authorize_procurement_batch)

_g.add_edge(START, "validate_chemical_safety")
_g.add_edge("validate_chemical_safety", "determine_handling_requirements")
_g.add_edge("determine_handling_requirements", "authorize_procurement_batch")
_g.add_edge("authorize_procurement_batch", END)

graph = _g.compile()
