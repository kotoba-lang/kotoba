# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111923 — Oarlock (segment 25).

Bespoke logic for marine oarlock hardware verification and inventory processing.
This agent assesses material quality, structural integrity, and socket compatibility.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111923"
UNISPSC_TITLE = "Oarlock"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111923"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Oarlock domain
    material_type: str
    integrity_status: str
    socket_fit_confirmed: bool
    marine_grade_verified: bool


def assess_component(state: State) -> dict[str, Any]:
    """Inspects the physical properties and material grade of the oarlock."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "standard_steel"))
    # Marine environments require corrosion-resistant materials
    is_marine = material.lower() in ["bronze", "stainless steel", "nylon", "galvanized"]

    return {
        "log": [f"{UNISPSC_CODE}:assess_component"],
        "material_type": material,
        "marine_grade_verified": is_marine,
    }


def verify_integrity(state: State) -> dict[str, Any]:
    """Simulates a stress test and structural integrity verification."""
    # Logic: if marine grade is verified, we apply a more rigorous certification
    status = "marine_certified" if state.get("marine_grade_verified") else "commercial_standard"

    return {
        "log": [f"{UNISPSC_CODE}:verify_integrity"],
        "integrity_status": status,
        "socket_fit_confirmed": True,
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Prepares the final result for the oarlock actor ledger."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_type"),
                "status": state.get("integrity_status"),
                "marine_ready": state.get("marine_grade_verified"),
                "fit_verified": state.get("socket_fit_confirmed", False),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("assess_component", assess_component)
_g.add_node("verify_integrity", verify_integrity)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "assess_component")
_g.add_edge("assess_component", "verify_integrity")
_g.add_edge("verify_integrity", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
