# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102101 — Cargo (segment 24).

Bespoke graph logic for Cargo management, handling manifest verification,
load safety checks, and logistics dispatch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102101"
UNISPSC_TITLE = "Cargo"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Cargo
    manifest_id: str
    weight_kg: float
    hazmat_clearance: bool
    is_bonded: bool


def inspect_manifest(state: State) -> dict[str, Any]:
    """Inspects the cargo manifest for valid identifiers and bonding status."""
    inp = state.get("input") or {}
    manifest_id = inp.get("manifest_id", "STB-000")
    is_bonded = inp.get("is_bonded", False)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_manifest: {manifest_id}"],
        "manifest_id": manifest_id,
        "is_bonded": is_bonded
    }


def verify_load_safety(state: State) -> dict[str, Any]:
    """Verifies weight limits and hazardous material declarations."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    hazmat = inp.get("hazmat", False)

    # Logic: if weight > 25000kg, additional safety protocols are logged
    safety_log = "standard_clearance" if weight < 25000 else "heavy_lift_required"

    return {
        "log": [f"{UNISPSC_CODE}:verify_load_safety: {safety_log}"],
        "weight_kg": weight,
        "hazmat_clearance": not hazmat or inp.get("hazmat_form_present", False)
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Finalizes the logistics dispatch record."""
    manifest = state.get("manifest_id")
    safe = state.get("hazmat_clearance", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch: manifest {manifest} ready"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "ready_for_transit" if safe else "held_for_safety",
            "manifest_ref": manifest,
            "ok": safe,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_manifest)
_g.add_node("verify", verify_load_safety)
_g.add_node("dispatch", finalize_dispatch)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
