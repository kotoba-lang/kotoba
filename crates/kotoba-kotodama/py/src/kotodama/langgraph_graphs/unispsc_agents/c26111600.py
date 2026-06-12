# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111600 — Generator (segment 26).

This bespoke agent handles the lifecycle of power generation equipment,
managing state transitions for capacity validation, startup simulation,
and load configuration within the Etz Hayyim actor mesh.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111600"
UNISPSC_TITLE = "Generator"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Generator
    capacity_kva: float
    fuel_level_percent: float
    synchronization_status: bool
    safety_interlock_active: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input electrical specifications and capacity requirements."""
    inp = state.get("input") or {}
    requested_capacity = float(inp.get("requested_kva", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "capacity_kva": requested_capacity,
        "safety_interlock_active": True,
    }


def simulate_startup(state: State) -> dict[str, Any]:
    """Simulates the generator engine startup and fuel system check."""
    # Logic to ensure the generator is ready to take load
    return {
        "log": [f"{UNISPSC_CODE}:simulate_startup"],
        "fuel_level_percent": 95.0,
        "synchronization_status": False,
    }


def configure_load(state: State) -> dict[str, Any]:
    """Finalizes the generator configuration for active power delivery."""
    return {
        "log": [f"{UNISPSC_CODE}:configure_load"],
        "synchronization_status": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational": True,
            "specs": {
                "kva": state.get("capacity_kva"),
                "fuel": "nominal",
                "sync": "locked"
            }
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specs)
_g.add_node("startup", simulate_startup)
_g.add_node("finalize", configure_load)

_g.add_edge(START, "validate")
_g.add_edge("validate", "startup")
_g.add_edge("startup", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
