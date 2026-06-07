# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191505 — Cargo (segment 25).

Bespoke logic for handling cargo manifests, weight validation, and logistics routing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191505"
UNISPSC_TITLE = "Cargo"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Cargo
    manifest_id: str
    weight_verification: bool
    hazmat_clearance: bool
    routing_path: str


def check_manifest(state: State) -> dict[str, Any]:
    """Validates the cargo manifest and extracts the identification."""
    inp = state.get("input") or {}
    manifest = inp.get("manifest", {})
    m_id = manifest.get("id", "UNKNOWN-MANIFEST")

    return {
        "log": [f"{UNISPSC_CODE}:check_manifest"],
        "manifest_id": m_id,
        "hazmat_clearance": manifest.get("has_hazmat", False) is False
    }


def verify_weight(state: State) -> dict[str, Any]:
    """Calculates weight constraints and verifies against vehicle capacity."""
    inp = state.get("input") or {}
    cargo = inp.get("cargo", {})
    weight = float(cargo.get("weight", 0.0))
    limit = float(cargo.get("limit", 20000.0))

    return {
        "log": [f"{UNISPSC_CODE}:verify_weight"],
        "weight_verification": weight <= limit,
        "routing_path": cargo.get("route", "DIRECT")
    }


def dispatch_cargo(state: State) -> dict[str, Any]:
    """Finalizes the cargo status and emits the shipment signal."""
    m_id = state.get("manifest_id", "N/A")
    weight_ok = state.get("weight_verification", False)
    hazmat_ok = state.get("hazmat_clearance", False)
    route = state.get("routing_path", "N/A")

    can_dispatch = weight_ok and hazmat_ok

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_cargo"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": can_dispatch,
            "dispatch_data": {
                "manifest_id": m_id,
                "route": route,
                "status": "APPROVED" if can_dispatch else "REJECTED"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("check_manifest", check_manifest)
_g.add_node("verify_weight", verify_weight)
_g.add_node("dispatch_cargo", dispatch_cargo)

_g.add_edge(START, "check_manifest")
_g.add_edge("check_manifest", "verify_weight")
_g.add_edge("verify_weight", "dispatch_cargo")
_g.add_edge("dispatch_cargo", END)

graph = _g.compile()
