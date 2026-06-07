# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101522 — Generator (segment 23).
Bespoke logic for power generation equipment specifications and load simulation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101522"
UNISPSC_TITLE = "Generator"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101522"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Generator
    power_rating_kva: float
    fuel_type: str
    is_standby: bool
    efficiency_rating: float
    load_validation_ok: bool


def inspect_parameters(state: State) -> dict[str, Any]:
    """Validates the input specifications for the generator unit."""
    inp = state.get("input") or {}
    # Extract power rating, default to 0.0 if not provided or invalid
    try:
        power = float(inp.get("power_rating_kva", 0.0))
    except (ValueError, TypeError):
        power = 0.0

    fuel = str(inp.get("fuel_type", "diesel"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_parameters"],
        "power_rating_kva": power,
        "fuel_type": fuel,
        "is_standby": bool(inp.get("is_standby", True)),
    }


def simulate_load(state: State) -> dict[str, Any]:
    """Simulates performance under requested load conditions."""
    power = state.get("power_rating_kva", 0.0)
    # Determine efficiency based on size category
    efficiency = 0.88 if power < 250 else 0.94

    # Validation logic: requires non-zero power rating
    valid = power > 0.0
    return {
        "log": [f"{UNISPSC_CODE}:simulate_load"],
        "efficiency_rating": efficiency,
        "load_validation_ok": valid,
    }


def finalize_specs(state: State) -> dict[str, Any]:
    """Compiles the final technical specification for the Generator actor."""
    is_ok = state.get("load_validation_ok", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specs"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "power_kva": state.get("power_rating_kva"),
                "fuel": state.get("fuel_type"),
                "efficiency": state.get("efficiency_rating"),
                "standby": state.get("is_standby"),
            },
            "status": "validated" if is_ok else "invalid_input",
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_parameters)
_g.add_node("simulate", simulate_load)
_g.add_node("finalize", finalize_specs)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "simulate")
_g.add_edge("simulate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
