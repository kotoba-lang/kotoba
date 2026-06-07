# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172404 — Storage (segment 25).

Bespoke graph logic for vehicle-specific storage systems and component allocation.
This agent handles validation, capacity assessment, and allocation finalization
for vehicular storage units and transport containers.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172404"
UNISPSC_TITLE = "Storage"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172404"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    storage_type: str
    volume_capacity: float
    security_level: int
    is_allocated: bool


def validate_storage_request(state: State) -> dict[str, Any]:
    """Inspects the input for storage specifications."""
    inp = state.get("input") or {}
    s_type = inp.get("storage_type", "standard_compartment")
    return {
        "log": [f"{UNISPSC_CODE}:validate_storage_request"],
        "storage_type": s_type,
    }


def calculate_available_space(state: State) -> dict[str, Any]:
    """Mocks a lookup for available vehicular storage capacity."""
    s_type = state.get("storage_type")
    # Simulation: overhead bins have less capacity than trunk compartments
    capacity = 1500.0 if s_type == "overhead" else 5000.0
    sec_level = 2 if s_type == "secure_vault" else 1
    return {
        "log": [f"{UNISPSC_CODE}:calculate_available_space"],
        "volume_capacity": capacity,
        "security_level": sec_level,
    }


def finalize_allocation(state: State) -> dict[str, Any]:
    """Records the allocation and prepares the final agent result."""
    cap = state.get("volume_capacity") or 0.0
    allocated = cap > 0
    return {
        "log": [f"{UNISPSC_CODE}:finalize_allocation"],
        "is_allocated": allocated,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "allocation_report": {
                "type": state.get("storage_type"),
                "capacity": cap,
                "security": state.get("security_level"),
                "status": "confirmed" if allocated else "failed"
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_storage_request)
_g.add_node("calculate", calculate_available_space)
_g.add_node("finalize", finalize_allocation)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
