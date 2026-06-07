# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101107 — Motor (segment 26).

Bespoke logic for managing motor specifications, performance diagnostics,
and operational status reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101107"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101107"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Motor
    voltage_rating: float
    rated_rpm: int
    load_factor: float
    health_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates motor electrical ratings from the provided input."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 400.0))
    rpm = int(inp.get("rpm", 1800))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs (V={voltage}, RPM={rpm})"],
        "voltage_rating": voltage,
        "rated_rpm": rpm,
        "health_status": "initialized",
    }


def analyze_performance(state: State) -> dict[str, Any]:
    """Simulates performance analysis under nominal load."""
    voltage = state.get("voltage_rating", 0.0)
    rpm = state.get("rated_rpm", 0)
    # Simple health check logic
    status = "nominal" if voltage > 0 and rpm > 0 else "degraded"
    return {
        "log": [f"{UNISPSC_CODE}:analyze_performance (status={status})"],
        "load_factor": 0.85,
        "health_status": status,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Produces the final diagnostic result for the Motor actor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "data": {
                "voltage": state.get("voltage_rating"),
                "rpm": state.get("rated_rpm"),
                "load": state.get("load_factor"),
                "health": state.get("health_status"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("analyze", analyze_performance)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
