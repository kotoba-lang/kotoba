# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111606 — Generator (segment 26).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111606"
UNISPSC_TITLE = "Generator"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    power_rating_kva: float
    fuel_type: str
    engine_rpm: int
    operational_status: str


def validate_config(state: State) -> dict[str, Any]:
    """Validate generator configuration and initialize parameters."""
    inp = state.get("input") or {}
    power = float(inp.get("power_kva", 500.0))
    fuel = str(inp.get("fuel", "natural gas"))
    return {
        "log": [f"{UNISPSC_CODE}:validate_config"],
        "power_rating_kva": power,
        "fuel_type": fuel,
    }


def simulate_operation(state: State) -> dict[str, Any]:
    """Calculate operational parameters like RPM based on power rating."""
    power = state.get("power_rating_kva", 0.0)
    # Basic logic: higher power generators often run at specific RPMs
    rpm = 1800 if power > 100 else 3600
    status = "standby" if rpm > 0 else "off"
    return {
        "log": [f"{UNISPSC_CODE}:simulate_operation"],
        "engine_rpm": rpm,
        "operational_status": status,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Produce the final agent result with generator metadata."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "generator_specs": {
                "kva": state.get("power_rating_kva"),
                "fuel": state.get("fuel_type"),
                "rpm": state.get("engine_rpm"),
                "status": state.get("operational_status"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_config)
_g.add_node("simulate", simulate_operation)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "simulate")
_g.add_edge("simulate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
