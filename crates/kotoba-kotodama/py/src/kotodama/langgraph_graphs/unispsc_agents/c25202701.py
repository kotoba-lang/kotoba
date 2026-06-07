# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202701 — Accumulator (segment 25).

Bespoke graph logic for managing pressure and charge state of an accumulator
component, simulating inspection, charging, and diagnostic reporting.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202701"
UNISPSC_TITLE = "Accumulator"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Accumulator
    current_pressure_bar: float
    max_pressure_bar: float
    is_fully_charged: bool
    membrane_integrity: float


def inspect_accumulator(state: State) -> dict[str, Any]:
    """Inspects initial state and parameters from input."""
    inp = state.get("input") or {}
    max_p = float(inp.get("max_pressure", 250.0))
    initial_p = float(inp.get("initial_pressure", 0.0))
    return {
        "log": [f"{UNISPSC_CODE}:inspect_accumulator"],
        "max_pressure_bar": max_p,
        "current_pressure_bar": initial_p,
        "membrane_integrity": 1.0,
        "is_fully_charged": initial_p >= max_p,
    }


def charge_cycle(state: State) -> dict[str, Any]:
    """Simulates a charging operation to increase internal pressure."""
    curr = state.get("current_pressure_bar", 0.0)
    max_p = state.get("max_pressure_bar", 250.0)

    # Increase pressure towards max capacity
    new_pressure = min(max_p, curr + 50.0)
    charged = new_pressure >= max_p

    return {
        "log": [f"{UNISPSC_CODE}:charge_cycle"],
        "current_pressure_bar": new_pressure,
        "is_fully_charged": charged,
    }


def report_diagnostics(state: State) -> dict[str, Any]:
    """Compiles final metrics and status into the result dictionary."""
    curr = state.get("current_pressure_bar", 0.0)
    max_p = state.get("max_pressure_bar", 250.0)
    charged = state.get("is_fully_charged", False)

    return {
        "log": [f"{UNISPSC_CODE}:report_diagnostics"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "ready" if charged else "charging",
            "metrics": {
                "pressure_bar": curr,
                "utilization": (curr / max_p) if max_p > 0 else 0.0,
                "integrity": state.get("membrane_integrity"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_accumulator)
_g.add_node("charge", charge_cycle)
_g.add_node("report", report_diagnostics)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "charge")
_g.add_edge("charge", "report")
_g.add_edge("report", END)

graph = _g.compile()
