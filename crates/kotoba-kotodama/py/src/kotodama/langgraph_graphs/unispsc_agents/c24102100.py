# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102100 — Warehouse (segment 24).
Provides bespoke storage logic for inventory management and dock assignment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102100"
UNISPSC_TITLE = "Warehouse"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Warehouse domain state fields
    manifest_id: str
    dock_assignment: str
    storage_bin: str
    weight_capacity_kg: float
    hazard_class: str


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the inbound shipment manifest and safety metadata."""
    inp = state.get("input") or {}
    manifest = str(inp.get("manifest", "M-UNKNOWN"))
    weight = float(inp.get("weight", 0.0))
    hazard = str(inp.get("hazard", "none"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest:{manifest}"],
        "manifest_id": manifest,
        "weight_capacity_kg": weight,
        "hazard_class": hazard
    }


def optimize_allocation(state: State) -> dict[str, Any]:
    """Determines the optimal dock and storage bin based on cargo type."""
    hazard = state.get("hazard_class", "none")
    weight = state.get("weight_capacity_kg", 0.0)

    # Simple rule-based allocation
    dock = "DOCK-HAZ" if hazard != "none" else "DOCK-STD"
    zone = "HEAVY" if weight > 1000 else "SHELF"
    bin_id = f"{zone}-{state.get('manifest_id', '000')[-3:]}"

    return {
        "log": [f"{UNISPSC_CODE}:optimize_allocation:dock={dock}:bin={bin_id}"],
        "dock_assignment": dock,
        "storage_bin": bin_id
    }


def commit_to_ledger(state: State) -> dict[str, Any]:
    """Finalizes the warehouse entry and sets the result payload."""
    return {
        "log": [f"{UNISPSC_CODE}:commit_to_ledger"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "manifest": state.get("manifest_id"),
            "location": {
                "dock": state.get("dock_assignment"),
                "bin": state.get("storage_bin")
            },
            "status": "committed",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_manifest)
_g.add_node("allocate", optimize_allocation)
_g.add_node("commit", commit_to_ledger)

_g.add_edge(START, "validate")
_g.add_edge("validate", "allocate")
_g.add_edge("allocate", "commit")
_g.add_edge("commit", END)

graph = _g.compile()
