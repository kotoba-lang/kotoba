# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111509 — Water Bag (segment 24).

This module provides bespoke logic for the inspection, stress testing, and
certification of water bag products. It follows the standard LangGraph
StateGraph pattern for automated process validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111509"
UNISPSC_TITLE = "Water Bag"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Water Bag
    material_grade: str
    capacity_liters: float
    integrity_status: bool
    batch_serial: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the material and capacity specifications of the water bag."""
    inp = state.get("input") or {}
    grade = inp.get("material", "LDPE-Food-Grade")
    volume = float(inp.get("capacity", 2.0))
    serial = inp.get("serial", "WB-00000")

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material_grade": grade,
        "capacity_liters": volume,
        "batch_serial": serial,
    }


def perform_leak_test(state: State) -> dict[str, Any]:
    """Simulates a pressure-based leak and integrity test."""
    grade = state.get("material_grade", "")
    # Higher grade materials have higher pass rates in this simulation
    is_valid = grade in ["LDPE-Food-Grade", "TPU-High-Strength", "BPA-Free-Nylon"]

    return {
        "log": [f"{UNISPSC_CODE}:perform_leak_test"],
        "integrity_status": is_valid,
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the processing and emits the certification result."""
    passed = state.get("integrity_status", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial": state.get("batch_serial"),
            "status": "CERTIFIED" if passed else "FAILED_INSPECTION",
            "specs": {
                "material": state.get("material_grade"),
                "volume_liters": state.get("capacity_liters"),
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("test", perform_leak_test)
_g.add_node("emit", certify_and_emit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
