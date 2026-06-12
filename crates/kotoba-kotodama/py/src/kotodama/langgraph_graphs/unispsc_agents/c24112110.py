# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112110 — I B C (Intermediate Bulk Containers).

This agent manages the lifecycle of Intermediate Bulk Containers, including
structural integrity verification, volume capacity checks, and material
compatibility for industrial transport and storage.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112110"
UNISPSC_TITLE = "I B C"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112110"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Intermediate Bulk Containers
    ibc_serial_number: str
    material_compatibility_score: float
    capacity_liters: float
    structural_integrity_verified: bool
    containment_type: str  # e.g., Composite, All-Steel, Plastic


def inspect_container(state: State) -> dict[str, Any]:
    """Node: Evaluates the physical specifications of the IBC unit."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "IBC-TEMP-000")
    material = inp.get("type", "HDPE-Composite")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_container:{serial}"],
        "ibc_serial_number": serial,
        "containment_type": material,
        "structural_integrity_verified": True
    }


def verify_load_capacity(state: State) -> dict[str, Any]:
    """Node: Calculates if the container meets the required volume and safety ratings."""
    # Simulation of capacity check for standard IBC sizes (usually 1000L)
    planned_load = state.get("input", {}).get("load_volume", 1000.0)
    max_capacity = 1040.0

    is_safe = planned_load <= max_capacity
    score = 0.95 if is_safe else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_load_capacity:{planned_load}L"],
        "capacity_liters": planned_load,
        "material_compatibility_score": score
    }


def certify_for_transport(state: State) -> dict[str, Any]:
    """Node: Finalizes the IBC state and produces the agent result."""
    is_valid = (
        state.get("structural_integrity_verified", False) and
        state.get("material_compatibility_score", 0.0) > 0.8
    )

    return {
        "log": [f"{UNISPSC_CODE}:certify_for_transport"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": is_valid,
            "metadata": {
                "serial": state.get("ibc_serial_number"),
                "material": state.get("containment_type"),
                "capacity": state.get("capacity_liters")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_container)
_g.add_node("verify", verify_load_capacity)
_g.add_node("certify", certify_for_transport)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
