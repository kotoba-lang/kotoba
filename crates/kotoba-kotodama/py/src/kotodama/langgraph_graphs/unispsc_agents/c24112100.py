# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112100 — Container.

Bespoke LangGraph implementation for managing container specifications and
compliance within the Material Handling and Storage segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112100"
UNISPSC_TITLE = "Container"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Container
    container_id: str
    material_type: str
    volume_capacity: float
    is_stackable: bool
    inspection_passed: bool


def initialize_container(state: State) -> dict[str, Any]:
    """Extracts container metadata from input and assigns a tracking ID."""
    inp = state.get("input") or {}
    c_id = inp.get("id", "CNT-DEFAULT-001")
    mat = inp.get("material", "High-Density Polyethylene")

    return {
        "log": [f"{UNISPSC_CODE}:initialize_container -> {c_id}"],
        "container_id": c_id,
        "material_type": mat,
        "inspection_passed": False
    }


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates physical properties against Material Handling standards."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity_liters", 0.0))
    stackable = bool(inp.get("stackable", True))

    # Simple logic: Containers > 1000L require extra inspection, but here we just flag it
    passed = capacity > 0 and len(state.get("material_type", "")) > 0

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications -> capacity:{capacity}L"],
        "volume_capacity": capacity,
        "is_stackable": stackable,
        "inspection_passed": passed
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Finalizes the container record and generates the DID-linked result."""
    status = "VALIDATED" if state.get("inspection_passed") else "PENDING"

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "container_id": state.get("container_id"),
        "status": status,
        "manifest": {
            "material": state.get("material_type"),
            "capacity": state.get("volume_capacity"),
            "stackable": state.get("is_stackable")
        },
        "ok": state.get("inspection_passed", False)
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest -> status:{status}"],
        "result": res
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_container)
_g.add_node("verify", verify_specifications)
_g.add_node("finalize", generate_manifest)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
