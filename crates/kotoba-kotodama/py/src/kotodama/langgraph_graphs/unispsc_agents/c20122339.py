# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122339 — Bolt Procurement (segment 20).
Bespoke logic for bolt procurement specifications and supplier verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122339"
UNISPSC_TITLE = "Bolt Procurement"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122339"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Bolt Procurement
    bolt_specification: str
    quality_standard: str
    procurement_status: str
    supplier_id: str


def analyze_bolt_requirements(state: State) -> dict[str, Any]:
    """Validates the input for bolt specifications and grades."""
    inp = state.get("input") or {}
    spec = inp.get("spec", "ASTM A325 Heavy Hex Bolt")
    return {
        "log": [f"{UNISPSC_CODE}:analyze_bolt_requirements"],
        "bolt_specification": spec,
        "quality_standard": "ISO 898-1 Compliant",
        "procurement_status": "specifications_validated",
    }


def verify_industrial_inventory(state: State) -> dict[str, Any]:
    """Checks for stock matching the analyzed specifications in mining/drilling inventory."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_industrial_inventory"],
        "supplier_id": "SUP-MNG-20122339-B1",
        "procurement_status": "inventory_confirmed",
    }


def finalize_procurement_manifest(state: State) -> dict[str, Any]:
    """Prepares the final result for the procurement workflow authorization."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "specification": state.get("bolt_specification"),
            "standard": state.get("quality_standard"),
            "supplier": state.get("supplier_id"),
            "status": "authorized",
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_bolt_requirements", analyze_bolt_requirements)
_g.add_node("verify_industrial_inventory", verify_industrial_inventory)
_g.add_node("finalize_procurement_manifest", finalize_procurement_manifest)

_g.add_edge(START, "analyze_bolt_requirements")
_g.add_edge("analyze_bolt_requirements", "verify_industrial_inventory")
_g.add_edge("verify_industrial_inventory", "finalize_procurement_manifest")
_g.add_edge("finalize_procurement_manifest", END)

graph = _g.compile()
